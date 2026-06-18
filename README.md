# 🕷️ Brand New Day — Hyderabad ticket watcher

Polls BookMyShow for **Spider-Man: Brand New Day** showtimes across Hyderabad,
ranks cinemas by distance from **Gachibowli**, and pushes an instant phone
alert the moment a new cinema (or a new showtime at a known cinema) starts
selling. First few cinemas are already listed for premium formats — this
catches the rest as they go live.

## How it works
- Hits BookMyShow's internal `showtimes-by-event` API for each of the next
  `DAYS_AHEAD` days.
- Computes straight-line distance from Gachibowli to each cinema; nearest
  first, with a 📍 flag for anything inside `PRIORITY_RADIUS_KM`.
- Keeps a `state.json` of what it has already seen, so you only get pinged for
  **genuinely new** listings — never the same cinema twice.
- On first launch it sends one summary of what's already live, then stays
  quiet until something changes.

## 1. Install
```bash
pip install -r requirements.txt
```

## 2. Find the event code (required)
1. Open the Brand New Day page on BookMyShow Hyderabad in a desktop browser.
2. Look at the URL — it ends in something like `/ET00XXXXXX`. That's the code.
   (If it's not in the URL: open DevTools → Network, reload, filter for
   `showtimes-by-event`, and read `eventCode` from the request.)
3. Put it in `config.py` → `EVENT_CODE`, and paste the page URL into
   `MOVIE_PAGE_URL`.

## 3. Set up phone alerts (pick one — or both)

**Option A — ntfy (simplest, ~1 min, no account):**
1. Install the **ntfy** app (iOS/Android).
2. Subscribe to a hard-to-guess topic, e.g. `spidey-hyd-9f3kd2x`.
3. Put that string in `config.py` → `NTFY_TOPIC`.

**Option B — Telegram (free, very reliable):**
1. In Telegram, message **@BotFather** → `/newbot` → copy the bot token into
   `TELEGRAM_BOT_TOKEN`.
2. Send any message to your new bot.
3. Get your chat id:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates"
   ```
   Find `"chat":{"id": <number>}` and put it in `TELEGRAM_CHAT_ID`.

Then verify:
```bash
python agent.py --test     # should buzz your phone
```

## 4. Run it
```bash
python agent.py            # runs forever, polling every ~2 min
python agent.py --once     # one scan (good for a first check)
```

## If BMS returns nothing / blocks you
BMS changes its internals from time to time. Two fixes, in order:
- **Refresh request values:** open the site in Chrome → DevTools → Network →
  the `showtimes-by-event` request → right-click → *Copy as cURL*. Lift
  `bmsId`, `token`, version and any headers into `config.py`.
- **Check parsing:** run `python agent.py --dump` to see the raw JSON. If
  venues look empty, the key names in `parse_venues()` (in `agent.py`) may have
  shifted — they're isolated and commented for easy tweaking.

Keep `POLL_INTERVAL_SEC` at 2 min or higher — hammering BMS risks an IP block,
which defeats the purpose.

## Run it 24/7 WITHOUT your laptop

### ✅ Recommended: GitHub Actions (free, nothing runs on your machine)
GitHub runs the scan on its own servers every 5 minutes. State is committed
back to the repo so each run remembers what it already saw.

1. **Make a repo** (keep it **public** — public repos get *unlimited* free
   Actions minutes; private repos cap at 2000/month, which this exceeds).
   Push these files to it. The included workflow is at
   `.github/workflows/watch.yml`.
2. **Edit the non-secret values** at the top of `watch.yml`: set `EVENT_CODE`
   and `MOVIE_PAGE_URL` (and tweak `HOME_LAT/LON`, `PRIORITY_RADIUS_KM` if you
   like). Commit.
3. **Add your notifier secrets**: repo → *Settings → Secrets and variables →
   Actions → New repository secret*. Add whichever you use:
   - `NTFY_TOPIC`  (simplest)
   - or `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
4. **Turn it on**: repo → *Actions* tab → enable workflows → open
   *spidey-watch* → *Run workflow* once to test. After that it runs itself
   every ~5 min.

Notes:
- Scheduled runs can lag a few minutes under GitHub load — fine here, since a
  newly-listed cinema stays listed; you'll still get pinged within minutes.
- GitHub auto-pauses schedules after 60 days of zero repo commits. This watch
  window is shorter than that, and new listings produce commits anyway, so it
  stays alive. (To force it: hit *Run workflow* in the Actions tab.)

### Alternatives
- **Spare Android phone + Termux** (free, truly always-on): install Termux,
  `pkg install python`, `pip install requests`, run `python agent.py`. Leave
  it plugged in. Runs the real loop with tighter polling than Actions.
- **Oracle Cloud Always Free VM** or a cheap VPS (Hetzner ~€4/mo): run the
  long-lived loop under systemd. Create `/etc/systemd/system/spidey.service`:
  ```ini
  [Unit]
  Description=Brand New Day BMS watcher
  After=network-online.target
  [Service]
  WorkingDirectory=/home/youruser/bms-spidey-agent
  ExecStart=/usr/bin/python3 agent.py
  Restart=always
  RestartSec=30
  [Install]
  WantedBy=multi-user.target
  ```
  ```bash
  sudo systemctl enable --now spidey
  journalctl -u spidey -f
  ```

## Tuning (config.py)
| Setting | What it does |
|---|---|
| `DAYS_AHEAD` | How many days of showtimes to scan |
| `PRIORITY_RADIUS_KM` | Cinemas within this get 📍 and sort to the top |
| `MAX_DISTANCE_KM` | Ignore cinemas farther than this (`None` = all of Hyderabad) |
| `POLL_INTERVAL_SEC` | Seconds between scans |
| `ALERT_NEW_SHOWTIMES` | Also alert when a known cinema adds showtimes |

Default home coordinates are Gachibowli (17.4400, 78.3489) — adjust if you want
to rank around a different spot.
