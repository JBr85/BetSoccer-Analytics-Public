# BetSoccer Analytics

A local Flask web app for analysing your own **Betfair Exchange** betting history.
You connect your own Betfair account, sync your bet history, and explore your
**real** profit & loss by market, odds band and date — all on your own machine.

> **Your data stays with you.** This repo ships **no betting data and no credentials**.
> Everything runs locally on `http://localhost:5005`. Your Betfair login is stored only
> on your own computer, encrypted, and is never committed to git.

## Features

- **Analytics — Real Data** — actual P&L and stakes from your synced bets, with filters
  for market, odds range and date. No staking simulation, just what really happened.
- **Data** — browse your synced bets in a table and de-duplicate.
- **Settings** — connect your Betfair account and sync your history.

## Requirements

- Python 3.9+
- A Betfair account with an **Application Key** (see Betfair's Developer Program)

## Setup

```bash
# 1. Clone
git clone https://github.com/<your-username>/betsoccer-analytics.git
cd betsoccer-analytics

# 2. Create a virtual environment (recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python app.py
```

Then open **http://localhost:5005** in your browser.

On Windows you can also just double-click **`start_app.bat`**.

## First run

1. Go to **Settings**.
2. Enter your Betfair **username**, **password**, and **Application Key**, then
   **Connect**. Credentials are saved locally in `betfair_config.json`, encrypted
   with a key generated in `.betfair.key` (both are git-ignored).
3. Set **Sync History** days back and press **Sync History** to pull your bets.
4. Open **Analytics — Real Data** to explore your numbers.

## Privacy & safety

- `bets.db`, `betfair_config.json`, `.betfair.key`, and any uploaded files are listed
  in `.gitignore` and will not be committed.
- The app makes outbound calls only to Betfair's API (when you sync) and, for league
  auto-detection, TheSportsDB. No analytics or telemetry.
- This is a personal analysis tool. It does **not** place bets.

## Disclaimer

For personal record-keeping and analysis only. Not financial advice. Gamble responsibly.
