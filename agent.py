#!/usr/bin/env python3
"""
Spider-Man: Brand New Day — BookMyShow Hyderabad watcher.

Polls BookMyShow's showtimes API for your movie across the next few days,
ranks cinemas by distance from Gachibowli, and pushes a phone alert the
moment a NEW cinema (or a new showtime at a known cinema) starts selling.

Usage:
    python agent.py            # run the watcher loop
    python agent.py --once     # do a single scan and exit (good for testing)
    python agent.py --dump     # print one raw API response (to debug parsing)
    python agent.py --test     # send a test notification and exit
"""

import argparse
import html
import json
import math
import os
import random
import sys
import time
from datetime import datetime, timedelta

import requests

import config

BMS_URL = "https://in.bookmyshow.com/api/movies-data/showtimes-by-event"


# ---------------------------------------------------------------------------
# Geo
# ---------------------------------------------------------------------------

def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between two lat/lon points."""
    if None in (lat1, lon1, lat2, lon2):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(r * 2 * math.asin(math.sqrt(a)), 1)


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# BookMyShow client
# ---------------------------------------------------------------------------

def bms_headers():
    return {
        "x-bms-id": config.BMS_ID,
        "x-region-code": config.REGION_CODE,
        "x-subregion-code": config.REGION_CODE,
        "x-region-slug": config.REGION_SLUG,
        "x-platform": "AND",
        "x-platform-code": "ANDROID",
        "x-app-code": "MOBAND2",
        "x-device-make": "Google-Pixel",
        "x-screen-height": "2392",
        "x-screen-width": "1440",
        "x-app-version": "14.3.4",
        "x-app-version-code": config.APP_VERSION_CODE,
        "x-network": "Android | WIFI",
        "x-latitude": str(config.HOME_LAT),
        "x-longitude": str(config.HOME_LON),
        "lang": "en",
        "User-Agent": "okhttp/4.9.3",
    }


def date_codes(days_ahead):
    today = datetime.now()
    return [(today + timedelta(days=i)).strftime("%Y%m%d") for i in range(days_ahead)]


def fetch_raw(date_code):
    params = {
        "appCode": "MOBAND2",
        "appVersion": config.APP_VERSION_CODE,
        "bmsId": config.BMS_ID,
        "token": config.BMS_TOKEN,
        "lat": config.HOME_LAT,
        "lon": config.HOME_LON,
        "query": "",
        "dateCode": date_code,
        "eventCode": config.EVENT_CODE,
        "regionCode": config.REGION_CODE,
        "subRegion": config.REGION_CODE,
    }
    resp = requests.get(BMS_URL, params=params, headers=bms_headers(), timeout=25)
    resp.raise_for_status()
    return resp.json()


def _availability(showtime):
    """Summarise seat availability for a single show in a short string."""
    cats = showtime.get("Categories") or []
    avail_total = 0
    max_total = 0
    has_numbers = False
    for c in cats:
        a = c.get("SeatsAvail") or c.get("AvailableSeats")
        m = c.get("MaxSeats") or c.get("TotalSeats")
        try:
            avail_total += int(a)
            has_numbers = True
        except (TypeError, ValueError):
            pass
        try:
            max_total += int(m)
        except (TypeError, ValueError):
            pass
    if has_numbers:
        if max_total:
            return f"{avail_total} seats free"
        return f"{avail_total} seats free"
    # Fallback to a status string if no numeric counts are present.
    status = showtime.get("AvailabilityStatus") or showtime.get("ShowStatus")
    return str(status) if status else "open"


def parse_venues(data, date_code):
    """Normalise the BMS response into a flat list of venue dicts.

    Defensive on purpose — BMS occasionally renames keys. Run `--dump`
    if results look empty so you can adjust the key names here.
    """
    venues = []
    show_details = data.get("ShowDetails") or []
    for sd in show_details:
        for v in (sd.get("Venues") or []):
            name = (v.get("VenueName")
                    or v.get("VenueNameWithSubRegion")
                    or "Unknown venue")
            code = v.get("VenueCode") or name
            lat = _to_float(v.get("Latitude") or v.get("VenueLatitude"))
            lon = _to_float(v.get("Longitude") or v.get("VenueLongitude"))
            shows = []
            for st in (v.get("ShowTimes") or []):
                t = st.get("ShowTime") or st.get("ShowTimeCode") or "?"
                shows.append({"time": t, "avail": _availability(st)})
            if not shows:
                continue
            dist = haversine_km(config.HOME_LAT, config.HOME_LON, lat, lon)
            venues.append({
                "name": name,
                "code": str(code),
                "date": date_code,
                "lat": lat,
                "lon": lon,
                "dist": dist,
                "shows": shows,
            })
    return venues


def scan_all_dates():
    """Fetch and parse every date in the window. Returns a list of venues."""
    all_venues = []
    for dc in date_codes(config.DAYS_AHEAD):
        try:
            data = fetch_raw(dc)
        except requests.RequestException as e:
            print(f"  ! fetch failed for {dc}: {e}", file=sys.stderr)
            continue
        all_venues.extend(parse_venues(data, dc))
        time.sleep(0.5)  # gentle spacing between date requests
    # Distance filter
    if config.MAX_DISTANCE_KM is not None:
        all_venues = [v for v in all_venues
                      if v["dist"] is None or v["dist"] <= config.MAX_DISTANCE_KM]
    # Nearest first; unknown distances sink to the bottom.
    all_venues.sort(key=lambda v: (v["dist"] is None, v["dist"] or 1e9))
    return all_venues


# ---------------------------------------------------------------------------
# State (so we only alert on genuinely new listings)
# ---------------------------------------------------------------------------

def key_for(v):
    return f"{v['date']}|{v['code']}"


def load_state():
    if os.path.exists(config.STATE_FILE):
        try:
            with open(config.STATE_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def save_state(state):
    tmp = config.STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, config.STATE_FILE)


def diff(venues, state):
    """Return (new_venues, venues_with_new_showtimes) given prior state."""
    new_venues, new_times = [], []
    for v in venues:
        k = key_for(v)
        current_times = sorted(s["time"] for s in v["shows"])
        if k not in state:
            new_venues.append(v)
        else:
            previously = set(state[k])
            added = [s for s in v["shows"] if s["time"] not in previously]
            if added and config.ALERT_NEW_SHOWTIMES:
                vc = dict(v)
                vc["shows"] = added
                new_times.append(vc)
    return new_venues, new_times


def commit(venues, state):
    for v in venues:
        state[key_for(v)] = sorted(s["time"] for s in v["shows"])


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def notify_telegram(text):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return False
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, timeout=15, data={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        })
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  ! telegram failed: {e}", file=sys.stderr)
        return False


def notify_ntfy(title, text):
    if not config.NTFY_TOPIC:
        return False
    url = f"{config.NTFY_SERVER.rstrip('/')}/{config.NTFY_TOPIC}"
    # ntfy uses plain text body; strip HTML tags for it.
    plain = text.replace("<b>", "").replace("</b>", "").replace("&amp;", "&")
    try:
        r = requests.post(url, timeout=15, data=plain.encode("utf-8"), headers={
            "Title": title.encode("utf-8"),
            "Priority": "high",
            "Tags": "spider",
            "Click": config.MOVIE_PAGE_URL,
        })
        r.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"  ! ntfy failed: {e}", file=sys.stderr)
        return False


def notify(title, html_text):
    sent = False
    sent |= notify_telegram(html_text)
    sent |= notify_ntfy(title, html_text)
    if not sent:
        print("  ! no notifier configured — printing instead:\n" + html_text,
              file=sys.stderr)
    return sent


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def pretty_date(date_code):
    try:
        return datetime.strptime(date_code, "%Y%m%d").strftime("%a %d %b")
    except ValueError:
        return date_code


def fmt_venue(v):
    near = "📍 " if (v["dist"] is not None and v["dist"] <= config.PRIORITY_RADIUS_KM) else ""
    dist = f" ({v['dist']} km)" if v["dist"] is not None else ""
    times = ", ".join(f"{s['time']} [{s['avail']}]" for s in v["shows"][:12])
    name = html.escape(v["name"])
    return (f"{near}<b>{name}</b>{dist}\n"
            f"   {pretty_date(v['date'])}: {html.escape(times)}")


def build_alert(new_venues, new_times):
    parts = []
    if new_venues:
        parts.append("🕷️ <b>NEW cinema(s) now selling Brand New Day!</b>")
        parts += [fmt_venue(v) for v in new_venues]
    if new_times:
        if parts:
            parts.append("")
        parts.append("➕ <b>New showtimes added:</b>")
        parts += [fmt_venue(v) for v in new_times]
    parts.append(f"\n👉 Book: {config.MOVIE_PAGE_URL}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_dump():
    dc = date_codes(1)[0]
    print(f"Raw response for dateCode={dc}, eventCode={config.EVENT_CODE}:\n")
    print(json.dumps(fetch_raw(dc), indent=2)[:8000])


def cmd_test():
    ok = notify("Spidey watcher test",
                "🕷️ <b>Test alert</b>\nIf you can read this on your phone, "
                "notifications are working.")
    print("Test notification sent." if ok else "No notifier configured.")


def scan_and_alert(state, first_run):
    venues = scan_all_dates()
    print(f"  scan: {len(venues)} venue/date listings found")

    if first_run:
        # Don't spam an alert for everything already listed. Record current
        # state and send ONE concise summary of what's live right now.
        commit(venues, state)
        save_state(state)
        if venues:
            top = venues[:10]
            body = ["🕷️ <b>Watcher started.</b> Currently listed (nearest first):"]
            body += [fmt_venue(v) for v in top]
            if len(venues) > len(top):
                body.append(f"...and {len(venues) - len(top)} more.")
            body.append(f"\n👉 {config.MOVIE_PAGE_URL}")
            notify("Spidey watcher started", "\n".join(body))
        else:
            print("  (nothing listed yet — will alert as cinemas appear)")
        return

    new_venues, new_times = diff(venues, state)
    if new_venues or new_times:
        print(f"  ALERT: {len(new_venues)} new venue(s), "
              f"{len(new_times)} venue(s) with new times")
        notify("New Spider-Man tickets in Hyderabad!",
               build_alert(new_venues, new_times))
    commit(venues, state)
    save_state(state)


def main():
    ap = argparse.ArgumentParser(description="BookMyShow Spider-Man watcher")
    ap.add_argument("--once", action="store_true", help="single scan then exit")
    ap.add_argument("--dump", action="store_true", help="print one raw API response")
    ap.add_argument("--test", action="store_true", help="send a test notification")
    args = ap.parse_args()

    if args.dump:
        cmd_dump()
        return
    if args.test:
        cmd_test()
        return

    if config.EVENT_CODE == "ET00000000":
        print("ERROR: set EVENT_CODE in config.py first (see README).",
              file=sys.stderr)
        sys.exit(1)

    state = load_state()
    first_run = not os.path.exists(config.STATE_FILE)

    if args.once:
        scan_and_alert(state, first_run)
        return

    print(f"Watching Brand New Day in {config.REGION_SLUG}. "
          f"Polling every ~{config.POLL_INTERVAL_SEC}s. Ctrl-C to stop.")
    while True:
        try:
            stamp = datetime.now().strftime("%H:%M:%S")
            print(f"[{stamp}] scanning...")
            scan_and_alert(state, first_run)
            first_run = False
        except KeyboardInterrupt:
            print("\nStopped.")
            break
        except Exception as e:  # keep the loop alive through transient errors
            print(f"  ! loop error: {e}", file=sys.stderr)
        time.sleep(config.POLL_INTERVAL_SEC + random.uniform(0, config.JITTER_SEC))


if __name__ == "__main__":
    main()
