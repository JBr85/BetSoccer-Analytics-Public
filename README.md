# BetSoccer Analytics

A local Flask web app for analysing your own **Betfair Exchange** betting history.
You connect your own Betfair account (or upload a CSV/PDF export), sync your bet
history, and explore your **real** profit & loss by market, odds band and date —
all on your own machine.

> **Your data stays with you.** This repo ships **no betting data and no credentials**.
> Everything runs locally on `http://localhost:5005`. Your Betfair login is stored only
> on your own computer, encrypted, and is never committed to git.

---

## Table of contents

1. [What you get](#what-you-get)
2. [Before you start](#before-you-start)
3. [Install & run (step by step)](#install--run-step-by-step)
4. [Using the app — start to finish](#using-the-app--start-to-finish)
5. [Stopping and re-running it later](#stopping-and-re-running-it-later)
6. [Troubleshooting](#troubleshooting)
7. [Privacy & safety](#privacy--safety)
8. [Disclaimer](#disclaimer)

---

## What you get

The app has three pages, shown in the left sidebar:

- **Data** — browse every bet in a table; search, filter by sport/source, import
  CSV/PDF files, auto-detect leagues, de-duplicate, and delete rows.
- **Analytics — Real Data** — your actual P&L and stakes from your synced bets,
  with filters for market, odds range and date. No staking simulation — just what
  really happened.
- **Settings** — connect your Betfair account and sync your history.

---

## Before you start

You need two things:

1. **Python 3.9 or newer** installed.
   - Check by opening a terminal and running `python --version`.
   - Don't have it? Download from [python.org/downloads](https://www.python.org/downloads/).
     On Windows, **tick "Add Python to PATH"** during install.
2. **Your Betfair data.** Either:
   - A **Betfair Application Key** (free from the
     [Betfair Developer Program](https://developer.betfair.com/)) so the app can
     sync directly, **or**
   - A **CSV/PDF export** of your bets from your Betfair account — no developer
     key needed if you just want to upload a file.

> You can start with a CSV/PDF upload and add live syncing later. Either path works.

---

## Install & run (step by step)

### Windows — the easy way

1. Download this project (green **Code → Download ZIP** button on GitHub) and
   unzip it, or clone it (see below).
2. Open the unzipped folder.
3. Open a terminal **in that folder** and run the setup once:

   ```powershell
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

4. From now on, just **double-click `start_app.bat`**. It activates the
   environment, starts the server, and opens your browser at
   `http://localhost:5005` automatically.

### macOS / Linux — the easy way

1. Download or clone this project and open the folder in a terminal.
2. Run the setup once:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   chmod +x start_app.sh      # one-time: make the launcher executable
   ```

3. From now on, start it with **`./start_app.sh`**. Like the Windows `.bat`, it
   activates the environment, starts the server, and opens your browser at
   `http://localhost:5005` automatically.

### Windows / macOS / Linux — the manual way

```bash
# 1. Get the code
git clone https://github.com/<your-username>/betsoccer-analytics.git
cd betsoccer-analytics

# 2. Create an isolated environment (recommended, one-time)
python -m venv venv

#    Activate it:
venv\Scripts\activate        # Windows (PowerShell / cmd)
source venv/bin/activate     # macOS / Linux

# 3. Install dependencies (one-time, or after updates)
pip install -r requirements.txt

# 4. Start the app
python app.py
```

Then open **http://localhost:5005** in your browser.

You'll know it worked when the terminal shows something like
`Running on http://127.0.0.1:5005`. Leave that terminal window open — closing it
stops the app.

---

## Using the app — start to finish

### Step 1 — Open the app

Go to **http://localhost:5005**. You'll land on the **Data** page, which will be
empty until you add some bets.

### Step 2 — Get your bets in (choose one)

**Option A — Sync from Betfair (live):**

1. Click **Settings** in the sidebar.
2. Enter your Betfair **username**, **password**, and **Application Key**, then
   click **Connect**. Your credentials are saved locally in `betfair_config.json`,
   encrypted with a key generated in `.betfair.key` (both are git-ignored — they
   never leave your machine).
3. Set **how many days back** to pull, then click **Sync History**.
   The app fetches your bets and stores them in a local `bets.db` file.

> **Note:** Betfair's API requires **certificate authentication** for full bet
> history. If a basic sync returns nothing, use Option B (upload) instead — it
> works for everyone with no developer setup.

**Option B — Upload a CSV or PDF (no developer key needed):**

1. Export your bets from Betfair as a CSV or PDF.
2. Go to the **Data** page and click **Import CSV / PDF**, then choose your file.
3. The app parses it and adds the bets to your local database, then refreshes the
   table so you can see them straight away.

You can mix both — the **Data** page lets you filter by source (Betfair / CSV / PDF).

### Step 3 — Tidy your data (optional but recommended)

On the **Data** page you can:

- **Search** by match or bet type, and filter by **sport** or **source**.
- **Auto-detect leagues** for football bets (uses TheSportsDB to label competitions).
- **De-duplicate** — highlights and removes duplicate rows from overlapping syncs/uploads.
- **Delete** any rows you don't want included.

### Step 4 — Analyse

Click **Analytics — Real Data**. Here you see your genuine results:

- Total P&L and staked amounts.
- Breakdowns and filters by **market**, **odds range**, and **date**.

Adjust the filters to drill into, say, only football bets in a certain odds band,
or a specific date range.

### Step 5 — Refresh whenever you like

Re-sync (Option A) or upload a newer export (Option B) any time. Run the
de-duplicate step afterwards to keep the table clean.

---

## Stopping and re-running it later

- **To stop:** close the terminal window, or press `Ctrl + C` in it.
- **To run again later:**
  - Windows: double-click **`start_app.bat`**.
  - Manual: activate the environment (`venv\Scripts\activate` or
    `source venv/bin/activate`) and run `python app.py` again.

Your data and credentials persist locally between runs (in `bets.db` and
`betfair_config.json`), so you only set things up once.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `python` not found | Reinstall Python and tick **Add Python to PATH**, or try `python3`. |
| `pip install` fails | Make sure the virtual environment is **activated** first (you should see `(venv)` in your prompt). |
| Browser shows "can't connect" | The server isn't running. Start it (`python app.py` or `start_app.bat`) and wait for the `Running on...` line. |
| Port 5005 already in use | Another copy is already running — close it, or stop whatever is using port 5005. |
| Betfair sync returns 0 bets | Full history needs **certificate authentication**. Use the CSV/PDF upload on the **Data** page instead. |
| Lost / wrong credentials | Re-enter them in **Settings** and click **Connect** again. |

---

## Privacy & safety

- `bets.db`, `betfair_config.json`, `.betfair.key`, and any uploaded files are
  listed in `.gitignore` and will **not** be committed.
- Credentials are stored **encrypted** on your machine and are loaded only at runtime.
- The app makes outbound calls only to **Betfair's API** (when you sync) and, for
  league auto-detection, **TheSportsDB**. No analytics or telemetry.
- This is a personal analysis tool. It does **not** place bets.

---

## Disclaimer

For personal record-keeping and analysis only. Not financial advice. Gamble responsibly.
