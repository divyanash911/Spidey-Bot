"""
Configuration for the BookMyShow Spider-Man watcher.

Everything you need to edit lives here. Read the README first — the two
things you MUST fill in are EVENT_CODE and at least one notifier
(Telegram or ntfy). The BMS_* values can stay as-is to start; if BMS
rejects the requests, copy fresh ones from your browser (see README).
"""

# ---------------------------------------------------------------------------
# BookMyShow target
# ---------------------------------------------------------------------------

# Event code for "Spider-Man: Brand New Day" on BookMyShow.
# It looks like "ET00XXXXXX". See README -> "Finding the event code".
EVENT_CODE = "ET00447840"  # <-- REPLACE THIS

REGION_CODE = "HYD"
REGION_SLUG = "hyderabad"

# How many days ahead to scan (advance booking window). 7 is plenty for now.
DAYS_AHEAD = 7

# The movie page URL on BMS, used only to build a "tap to book" link in
# alerts. Paste the URL of the Hyderabad movie page. A generic fallback is
# fine if you don't have it yet.
MOVIE_PAGE_URL = "https://in.bookmyshow.com/explore/movies-hyderabad"

# ---------------------------------------------------------------------------
# Request identity
# These defaults often work. If you get empty/blocked responses, open the BMS
# site in Chrome, DevTools -> Network, find the "showtimes-by-event" request,
# right-click -> Copy as cURL, and lift the real values into here.
# ---------------------------------------------------------------------------

BMS_ID = "1.21345445.1632544234"        # x-bms-id / bmsId
BMS_TOKEN = "67x1xa33b4x422b361ba"      # public web token used by BMS
APP_VERSION_CODE = "14304"

# ---------------------------------------------------------------------------
# Your location (Gachibowli) — used to rank theatres by distance
# ---------------------------------------------------------------------------

HOME_LAT = 17.4400
HOME_LON = 78.3489

# Venues within this radius get a 📍 "near you" flag and are pushed to the top.
PRIORITY_RADIUS_KM = 8.0

# Set to a number (e.g. 25) to completely ignore venues farther than this.
# Set to None to be alerted about every venue in Hyderabad.
MAX_DISTANCE_KM = None

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

POLL_INTERVAL_SEC = 60*60*6   # base interval between full scans
JITTER_SEC = 30           # random 0..JITTER added each loop (be polite to BMS)

# Also alert when an already-seen cinema adds NEW showtimes (not just when a
# brand-new cinema appears). Set False if that feels too chatty.
ALERT_NEW_SHOWTIMES = True

# ---------------------------------------------------------------------------
# Notifications — fill in at least one
# ---------------------------------------------------------------------------

# --- Telegram (free, instant). See README for the 2-minute setup. ---
TELEGRAM_BOT_TOKEN = ""   # from @BotFather, looks like 123456:ABC-DEF...
TELEGRAM_CHAT_ID = ""     # your numeric chat id

# --- ntfy.sh (even simpler: install the app, subscribe to a topic) ---
NTFY_TOPIC = "spidey-hyd-9f3kd2x"           # any hard-to-guess string, e.g. "spidey-hyd-9f3kd2x"
NTFY_SERVER = "https://ntfy.sh"

# State file (tracks what we've already seen so you only get NEW alerts).
STATE_FILE = "state.json"
