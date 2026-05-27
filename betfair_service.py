"""
Betfair API Service Module
Handles authentication and fetching betting history from Betfair API
"""

import os
import re
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False

logger = logging.getLogger(__name__)

# Try to import betfairlightweight, provide fallback if not available
try:
    import betfairlightweight
    BETFAIR_SDK_AVAILABLE = True
except ImportError:
    BETFAIR_SDK_AVAILABLE = False
    logger.warning("betfairlightweight not installed. Betfair sync will be disabled.")


def normalize_event_type(et):
    """Map Betfair's event_type.name to the canonical sport label used in the DB.

    Examples:
        'Soccer'        -> 'Football'   (we call it Football in this app)
        'Horse Racing'  -> 'Horse Racing'
        'Golf'          -> 'Golf'
        'Tennis'        -> 'Tennis'
        ''              -> ''           (caller must fall back)
    """
    et = (et or '').strip()
    if not et:
        return ''
    low = et.lower()
    if low == 'soccer':
        return 'Football'
    if low == 'horse racing':
        return 'Horse Racing'
    return et.title()


class BetfairService:
    """Service class for Betfair API interactions"""
    
    def __init__(self, app=None):
        self.app = app
        self.username = None
        self.password = None
        self.app_key = None
        self.cert_file = None
        self.key_file = None
        self._trading = None
        self._load_credentials()
    
    def _get_fernet(self):
        key_path = Path('.betfair.key')
        if key_path.exists():
            key = key_path.read_bytes()
        else:
            key = Fernet.generate_key()
            key_path.write_bytes(key)
        return Fernet(key)

    def _encrypt(self, value):
        if not CRYPTO_AVAILABLE or not value:
            return value
        return self._get_fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value):
        if not CRYPTO_AVAILABLE or not value:
            return value
        try:
            return self._get_fernet().decrypt(value.encode()).decode()
        except Exception:
            # Value was stored unencrypted (migration path) — return as-is
            return value

    def _load_credentials(self):
        config_path = Path('betfair_config.json')
        if config_path.exists():
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    self.username = self._decrypt(config.get('username'))
                    self.password = self._decrypt(config.get('password'))
                    self.app_key = config.get('app_key', '')
                    self.cert_file = config.get('cert_file')
                    self.key_file = config.get('key_file')
                # Re-save if credentials were stored unencrypted
                if self.username and self.password:
                    self.save_credentials(self.username, self.password, self.app_key, self.cert_file, self.key_file)
            except Exception as e:
                logger.error(f"Error loading Betfair credentials: {e}")

    def save_credentials(self, username, password, app_key=None, cert_file=None, key_file=None):
        config = {
            'username': self._encrypt(username),
            'password': self._encrypt(password),
            'app_key': app_key or '',
            'cert_file': cert_file,
            'key_file': key_file
        }
        with open('betfair_config.json', 'w') as f:
            json.dump(config, f)
        self.username = username
        self.password = password
        self.app_key = config['app_key']
        self.cert_file = cert_file
        self.key_file = key_file
        return True
    
    def is_configured(self):
        """Check if Betfair credentials are configured"""
        return bool(self.username and self.password)

    def _ensure_connected(self):
        if self._trading and self._trading.session_token:
            return True
        ok, _ = self.connect()
        return ok

    def connect(self):
        """Connect to Betfair API"""
        if not BETFAIR_SDK_AVAILABLE:
            return False, "Betfair SDK not installed"

        if not self.is_configured():
            return False, "Betfair credentials not configured"

        try:
            from betfairlightweight import APIClient
            from betfairlightweight.exceptions import LoginError

            self._trading = APIClient(
                username=self.username,
                password=self.password,
                app_key=self.app_key,
            )

            self._trading.login_interactive()

            if self._trading.session_token:
                return True, "Connected successfully"
            else:
                self._trading = None
                return False, "Login failed: no session token received"

        except LoginError as e:
            logger.error(f"Betfair login error: {e}")
            self._trading = None
            return False, f"Login failed: {e}"
        except Exception as e:
            logger.error(f"Betfair connection error: {e}")
            self._trading = None
            return False, str(e)
    
    def get_bet_history(self, days_back=30):
        """Fetch betting history from Betfair"""
        if not self._trading or not self._trading.session_token:
            connected, msg = self.connect()
            if not connected:
                return [], msg

        try:
            from betfairlightweight.filters import time_range

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            logger.info(f"Fetching bet history from {start_date} to {end_date}")

            cleared_orders = self._trading.betting.list_cleared_orders(
                bet_status='SETTLED',
                settled_date_range=time_range(from_=start_date, to=end_date),
                include_item_description=True,
                record_count=1000,
            )

            if not cleared_orders or not cleared_orders.orders:
                return [], "No settled orders found in the specified period"

            # Batch-fetch market catalogues to get competition / country / market-type data
            competition_map = {}  # market_id -> {'competition', 'country_code', 'market_type'}
            market_ids = list({o.market_id for o in cleared_orders.orders if o.market_id})
            if market_ids:
                try:
                    from betfairlightweight.filters import market_filter as bf_filter
                    for i in range(0, len(market_ids), 100):
                        batch = market_ids[i:i + 100]
                        catalogues = self._trading.betting.list_market_catalogue(
                            filter=bf_filter(market_ids=batch),
                            market_projection=['COMPETITION', 'EVENT', 'EVENT_TYPE', 'MARKET_DESCRIPTION'],
                            max_results=len(batch),
                        )
                        for cat in catalogues:
                            mtype = None
                            if cat.description and cat.description.market_type:
                                mtype = cat.description.market_type
                            competition_map[cat.market_id] = {
                                'competition': cat.competition.name if cat.competition else '',
                                'country_code': cat.event.country_code if cat.event else '',
                                'market_type': mtype,
                                'event_type': cat.event_type.name if cat.event_type else '',
                            }
                except Exception as e:
                    logger.warning(f"Could not fetch market catalogues: {e}")

            parsed = []
            for order in cleared_orders.orders:
                event_name = ''
                runner_name = ''
                market_desc = ''
                if order.item_description:
                    event_name  = str(order.item_description.event_desc or '')
                    market_desc = str(order.item_description.market_desc or '')
                    runner_name = str(order.item_description.runner_desc or market_desc or '').replace("'", "")

                cat_info = competition_map.get(order.market_id, {})
                bf_event_type_raw = cat_info.get('event_type') or ''
                bf_event_type = bf_event_type_raw.lower()

                # Determine sport from Betfair's event_type when available; otherwise
                # fall back to event_desc time-prefix pattern. Preserves Golf, Tennis, etc.
                if bf_event_type_raw:
                    sport_name = normalize_event_type(bf_event_type_raw)
                    is_horse_racing = sport_name == 'Horse Racing'
                else:
                    is_horse_racing = bool(re.match(r'^\d{1,2}:\d{2}\s', event_name))
                    sport_name = 'Horse Racing' if is_horse_racing else 'Football'

                # bet_category (Win/Place) is only meaningful for Horse Racing.
                # For football set it to None so it doesn't pollute HR system tabs.
                if is_horse_racing:
                    if 'to be placed' in market_desc.lower():
                        bet_category = 'Place'
                    elif market_desc:
                        bet_category = 'Win'
                    else:
                        raw_mtype = cat_info.get('market_type') or ''
                        bet_category = {'WIN': 'Win', 'PLACE': 'Place'}.get(raw_mtype.upper()) if raw_mtype else None
                    market_field = 'Exchange'
                else:
                    bet_category = None
                    # Store the actual market name for football (e.g. "Match Odds", "Both Teams To Score")
                    market_field = market_desc or 'Exchange'

                # Capture all raw Betfair metrics for later display/analysis
                bf_raw_metrics = {
                    'bet_id': str(order.bet_id or ''),
                    'bet_count': order.bet_count,
                    'bet_outcome': str(order.bet_outcome or ''),
                    'event_id': str(order.event_id or ''),
                    'event_type_id': str(order.event_type_id or ''),
                    'handicap': order.handicap,
                    'last_matched_date': order.last_matched_date.isoformat() if order.last_matched_date else None,
                    'market_id': str(order.market_id or ''),
                    'order_type': str(order.order_type or ''),
                    'persistence_type': str(order.persistence_type or ''),
                    'price_reduced': order.price_reduced,
                    'price_requested': order.price_requested,
                    'commission': order.commission,
                    'selection_id': order.selection_id,
                    'settled_date': order.settled_date.isoformat() if order.settled_date else None,
                    'side': str(order.side or ''),
                    'size_cancelled': order.size_cancelled,
                    'customer_strategy_ref': str(order.customer_strategy_ref or ''),
                    'customer_order_ref': str(order.customer_order_ref or ''),
                    'item_description': {
                        'event_type_desc': str(order.item_description.event_type_desc or '') if order.item_description else '',
                        'market_type': str(order.item_description.market_type or '') if order.item_description else '',
                        'number_of_winners': order.item_description.number_of_winners if order.item_description else None,
                        'each_way_divisor': order.item_description.each_way_divisor if order.item_description else None,
                    },
                    'market_catalogue': {
                        'competition_name': cat_info.get('competition', ''),
                        'country_code': cat_info.get('country_code', ''),
                        'market_type': cat_info.get('market_type', ''),
                        'event_type': cat_info.get('event_type', ''),
                    }
                }

                record = {
                    'date': order.placed_date.isoformat() if order.placed_date else '',
                    'match': event_name or 'Unknown',
                    'bet_type': runner_name or 'Unknown',
                    'market': market_field,
                    'stake': float(order.size_settled or 0),
                    'matched': float(order.size_settled or 0),
                    'odds': float(order.price_matched or 0),
                    'status': 'Settled',
                    'pnl': float(order.profit or 0),
                    'country': '',
                    'league': '',
                    'bf_competition': cat_info.get('competition', ''),
                    'bf_country_code': cat_info.get('country_code', ''),
                    'bet_category': bet_category,
                    'sport': sport_name,
                    'source': 'betfair',
                    'bf_raw_data': json.dumps(bf_raw_metrics),
                }
                parsed.append(record)

            logger.info(f"Retrieved {len(parsed)} orders from Betfair")
            return parsed, "Success"

        except Exception as e:
            logger.error(f"Error fetching bet history: {e}")
            return [], str(e)
    
    def get_pending_orders(self):
        """Fetch all current (unmatched + matched-but-not-settled) orders from Betfair."""
        if not self._ensure_connected():
            return [], "Not connected to Betfair"
        try:
            result = self._trading.betting.list_current_orders(record_count=1000)
            if not result or not result.orders:
                return [], "No pending orders found"

            # Batch-fetch market catalogues for event/runner names
            market_ids = list({o.market_id for o in result.orders if o.market_id})
            catalogue_map = {}
            runner_map = {}
            if market_ids:
                try:
                    from betfairlightweight.filters import market_filter as bf_filter
                    for i in range(0, len(market_ids), 100):
                        batch = market_ids[i:i + 100]
                        catalogues = self._trading.betting.list_market_catalogue(
                            filter=bf_filter(market_ids=batch),
                            market_projection=['COMPETITION', 'EVENT', 'EVENT_TYPE', 'RUNNER_DESCRIPTION', 'MARKET_START_TIME'],
                            max_results=len(batch),
                        )
                        for cat in catalogues:
                            catalogue_map[cat.market_id] = cat
                            for runner in (cat.runners or []):
                                runner_map[(cat.market_id, runner.selection_id)] = runner.runner_name
                except Exception as e:
                    logger.warning(f"Could not fetch catalogues for pending orders: {e}", exc_info=True)

            # Batch-fetch best available back prices for all pending markets
            best_back_map = {}
            if market_ids:
                try:
                    from betfairlightweight.filters import price_projection, ex_best_offers_overrides
                    for i in range(0, len(market_ids), 40):
                        batch = market_ids[i:i + 40]
                        books = self._trading.betting.list_market_book(
                            market_ids=batch,
                            price_projection=price_projection(
                                price_data=['EX_BEST_OFFERS'],
                                ex_best_offers_overrides=ex_best_offers_overrides(best_prices_depth=1),
                            ),
                        )
                        for book in books:
                            for runner in book.runners:
                                if runner.ex and runner.ex.available_to_back:
                                    best_back_map[(book.market_id, runner.selection_id)] = \
                                        runner.ex.available_to_back[0].price
                except Exception as e:
                    logger.warning(f"Could not fetch market books for pending orders: {e}")

            parsed = []
            for order in result.orders:
                cat = catalogue_map.get(order.market_id)
                event_name, market_name, runner_name, bf_event_type_raw = '', '', '', ''
                if cat:
                    bf_event_type_raw = cat.event_type.name if cat.event_type else ''
                    market_name = cat.market_name or ''
                    venue = cat.event.name if cat.event else ''
                    if bf_event_type_raw.lower() == 'horse racing' and cat.market_start_time:
                        from datetime import timezone as _tz
                        start_utc = cat.market_start_time
                        if start_utc.tzinfo is None:
                            start_utc = start_utc.replace(tzinfo=_tz.utc)
                        local_start = start_utc.astimezone()
                        time_str = local_start.strftime('%H:%M')
                        event_name = f"{time_str} {venue}".strip() if venue else time_str
                    else:
                        event_name = venue
                runner_name = runner_map.get((order.market_id, order.selection_id), '')

                if bf_event_type_raw:
                    sport_name = normalize_event_type(bf_event_type_raw)
                    is_horse_racing = sport_name == 'Horse Racing'
                else:
                    is_horse_racing = bool(re.match(r'^\d{1,2}:\d{2}\s', event_name))
                    sport_name = 'Horse Racing' if is_horse_racing else 'Football'
                if is_horse_racing:
                    bet_category = 'Place' if 'place' in market_name.lower() else 'Win'
                    market_field = 'Exchange'
                else:
                    bet_category = None
                    market_field = market_name or 'Exchange'

                is_sp = str(order.order_type or '').upper() == 'MARKET_ON_CLOSE'
                price = 0
                if order.average_price_matched and float(order.average_price_matched) > 0:
                    price = float(order.average_price_matched)
                elif order.price_size and float(order.price_size.price or 0) > 0:
                    price = float(order.price_size.price)
                if price == 0:
                    price = best_back_map.get((order.market_id, order.selection_id), 0)

                size_matched   = float(order.size_matched or 0)
                size_remaining = float(order.size_remaining or 0)
                bsp_liability  = float(order.bsp_liability or 0)
                # LIMIT orders: matched + remaining; MOC/SP orders: bsp_liability
                stake = (size_matched + size_remaining) or bsp_liability

                parsed.append({
                    'id':           None,
                    'date':         order.placed_date.isoformat() if order.placed_date else '',
                    'match':        event_name or f'Market {order.market_id}',
                    'bet_type':     runner_name or 'Unknown',
                    'market':       market_field,
                    'stake':        stake,
                    'matched':      size_matched,
                    'odds':         price,
                    'is_sp':        is_sp,
                    'status':       'Pending',
                    'pnl':          0,
                    'country':      '',
                    'league':       '',
                    'source':       'betfair',
                    'sport':        sport_name,
                    'bet_category': bet_category,
                    'bf_bet_id':    str(order.bet_id or ''),
                })

            logger.info(f"Retrieved {len(parsed)} pending orders from Betfair")
            return parsed, "Success"

        except Exception as e:
            logger.error(f"Error fetching pending orders: {e}")
            return [], str(e)

    # ------------------------------------------------------------------ #
    #  BET PLACEMENT                                                       #
    # ------------------------------------------------------------------ #

    def search_horse_racing_markets(self, venue=None, race_date=None, race_time=None):
        """Return WIN and PLACE market catalogues for a venue/date.

        Makes two separate API calls (WIN then PLACE) so the market_type field
        is reliable without needing the MARKET_DESCRIPTION projection, which
        causes TOO_MUCH_DATA errors on broad queries.
        """
        if not self._ensure_connected():
            return None, "Not connected to Betfair"
        try:
            from betfairlightweight.filters import market_filter, time_range

            if race_date:
                if isinstance(race_date, str):
                    race_date = datetime.strptime(race_date[:10], '%Y-%m-%d')
                start = race_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end   = race_date.replace(hour=23, minute=59, second=59, microsecond=0)
            else:
                start = datetime.utcnow()
                end   = start + timedelta(hours=12)

            # Narrow countries when no venue supplied to avoid TOO_MUCH_DATA
            countries = ['GB', 'IE'] if not venue else ['GB', 'IE', 'US', 'AU', 'FR', 'ZA']

            projection = ['RUNNER_DESCRIPTION', 'EVENT', 'MARKET_START_TIME']

            def _fetch(type_code):
                kwargs = dict(
                    event_type_ids=['7'],
                    market_countries=countries,
                    market_type_codes=[type_code],
                    market_start_time=time_range(from_=start, to=end),
                )
                if venue:
                    kwargs['text_query'] = venue
                f = market_filter(**kwargs)
                cats = self._trading.betting.list_market_catalogue(
                    filter=f,
                    market_projection=projection,
                    sort='FIRST_TO_START',
                    max_results=100,
                )
                # Tag each catalogue with the queried type so find_runner knows
                for cat in cats:
                    cat._queried_market_type = type_code
                return cats

            win_cats   = _fetch('WIN')
            place_cats = _fetch('PLACE')
            return win_cats + place_cats, "OK"

        except Exception as e:
            logger.error(f"Error searching markets: {e}")
            return None, str(e)

    def find_runner(self, horse_name, catalogues):
        """Search catalogues for a runner matching horse_name. Returns list of match dicts."""
        needle = horse_name.replace("'", "").lower().strip()
        results = []
        for cat in catalogues:
            if not cat.runners:
                continue
            # Use the tag set by search_horse_racing_markets (reliable, no extra projection needed)
            market_type = getattr(cat, '_queried_market_type', None)
            if not market_type:
                if cat.description and cat.description.market_type:
                    market_type = cat.description.market_type
                else:
                    market_type = 'PLACE' if 'place' in (cat.market_name or '').lower() else 'WIN'
            for runner in cat.runners:
                rn = (runner.runner_name or '').replace("'", "").lower().strip()
                if rn == needle or needle in rn or rn in needle:
                    results.append({
                        'market_id':    cat.market_id,
                        'market_name':  cat.market_name or '',
                        'market_type':  market_type,
                        'start_time':   cat.market_start_time.isoformat() if cat.market_start_time else None,
                        'event_name':   cat.event.name if cat.event else '',
                        'selection_id': runner.selection_id,
                        'runner_name':  runner.runner_name or '',
                        'handicap':     runner.handicap or 0,
                        'runner_count': len(cat.runners),
                        'best_back_price': self._best_back(cat.market_id, runner.selection_id),
                    })
        return results

    def _best_back(self, market_id, selection_id):
        """Return the current best available back price, or None."""
        try:
            from betfairlightweight.filters import price_projection, ex_best_offers_overrides
            books = self._trading.betting.list_market_book(
                market_ids=[market_id],
                price_projection=price_projection(
                    price_data=['EX_BEST_OFFERS'],
                    ex_best_offers_overrides=ex_best_offers_overrides(best_prices_depth=1),
                ),
            )
            if not books:
                return None
            for runner in books[0].runners:
                if runner.selection_id == selection_id:
                    if runner.ex and runner.ex.available_to_back:
                        return runner.ex.available_to_back[0].price
        except Exception as e:
            logger.debug(f"Could not fetch best back price: {e}")
        return None

    def get_market_descriptions(self, market_ids):
        """Fetch MARKET_DESCRIPTION for a specific list of market IDs.

        Returns dict: market_id -> {'number_of_winners': int, 'each_way_divisor': float|None, 'rules': str|None}
        Safe to call on a small set of IDs — no TOO_MUCH_DATA risk.
        """
        if not market_ids or not self._ensure_connected():
            return {}
        try:
            from betfairlightweight.filters import market_filter as bf_filter
            ids = list(market_ids)
            cats = self._trading.betting.list_market_catalogue(
                filter=bf_filter(market_ids=ids),
                market_projection=['MARKET_DESCRIPTION'],
                max_results=len(ids),
            )
            result = {}
            for cat in cats:
                if cat.description:
                    result[cat.market_id] = {
                        'number_of_winners': cat.description.number_of_winners,
                        'each_way_divisor':  cat.description.each_way_divisor,
                        'rules':             getattr(cat.description, 'rules', None),
                    }
            return result
        except Exception as e:
            logger.error(f"Error fetching market descriptions: {e}")
            return {}

    def place_exchange_bets(self, bet_list):
        """
        Place bets on Betfair Exchange.

        Each item in bet_list must contain:
          market_id, selection_id, handicap, side ('BACK'/'LAY'),
          order_type ('LIMIT' | 'MARKET_ON_CLOSE'),
          stake (float),
          price (float, required for LIMIT orders),
          horse_name (str, for reporting only)

        Returns (results_list, message).
        """
        if not self._ensure_connected():
            return None, "Not connected to Betfair"

        from collections import defaultdict
        market_bets = defaultdict(list)
        for i, bet in enumerate(bet_list):
            market_bets[bet['market_id']].append((i, bet))

        results = []
        for market_id, bets in market_bets.items():
            try:
                from betfairlightweight.filters import (
                    place_instruction, limit_order, market_on_close_order
                )
                instructions = []
                for _idx, bet in bets:
                    if bet.get('order_type') == 'MARKET_ON_CLOSE':
                        moc   = market_on_close_order(liability=float(bet['stake']))
                        instr = place_instruction(
                            order_type='MARKET_ON_CLOSE',
                            selection_id=bet['selection_id'],
                            side=bet.get('side', 'BACK'),
                            handicap=bet.get('handicap', 0),
                            market_on_close_order=moc,
                        )
                    else:
                        lo    = limit_order(
                            size=float(bet['stake']),
                            price=float(bet['price']),
                            persistence_type=bet.get('persistence', 'LAPSE'),
                        )
                        instr = place_instruction(
                            order_type='LIMIT',
                            selection_id=bet['selection_id'],
                            side=bet.get('side', 'BACK'),
                            handicap=bet.get('handicap', 0),
                            limit_order=lo,
                        )
                    instructions.append(instr)

                response = self._trading.betting.place_orders(
                    market_id=market_id,
                    instructions=instructions,
                    customer_ref=f'bst_{market_id.replace(".", "")[:15]}',
                )

                for i, report in enumerate(response.place_instruction_reports):
                    orig_idx, orig_bet = bets[i]
                    results.append({
                        'index':        orig_idx,
                        'status':       report.status,
                        'bet_id':       report.bet_id if hasattr(report, 'bet_id') else None,
                        'error':        report.error_code if report.status != 'SUCCESS' else None,
                        'market_id':    market_id,
                        'selection_id': orig_bet['selection_id'],
                        'horse':        orig_bet.get('horse_name', ''),
                        'stake':        orig_bet['stake'],
                        'price':        orig_bet.get('price', 'SP'),
                        'order_type':   orig_bet.get('order_type', 'LIMIT'),
                        'market_type':  orig_bet.get('market_type', 'WIN'),
                    })

            except Exception as e:
                logger.error(f"Error placing orders for market {market_id}: {e}")
                for orig_idx, orig_bet in bets:
                    results.append({
                        'index':     orig_idx,
                        'status':    'FAILURE',
                        'error':     str(e),
                        'market_id': market_id,
                        'horse':     orig_bet.get('horse_name', ''),
                    })

        return results, "Done"

    def parse_betfair_orders(self, orders_data):
        """Parse Betfair order data into our format"""
        parsed = []
        
        for order in orders_data:
            try:
                record = {
                    'date': order.get('placedDate', ''),
                    'match': order.get('selectionName', 'Unknown'),
                    'bet_type': order.get('marketName', 'Unknown'),
                    'stake': float(order.get('size', 0)),
                    'odds': float(order.get('price', 0)),
                    'status': 'Settled' if order.get('settledDate') else 'Open',
                    'pnl': float(order.get('profit', 0)),
                    'source': 'betfair'
                }
                parsed.append(record)
            except Exception as e:
                logger.warning(f"Error parsing order: {e}")
                continue
        
        return parsed


# Singleton instance
_betfair_service = None


def get_betfair_service():
    """Get or create Betfair service singleton"""
    global _betfair_service
    if _betfair_service is None:
        _betfair_service = BetfairService()
    return _betfair_service