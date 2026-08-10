#!/usr/bin/env python3
"""
Calipokehouse eBay -> Discord notifier.

Time-based (no live detection): fires each scheduled shift once per calendar
day, within a ~30 minute window after the scheduled hour. Designed to be
triggered by cron-job.org pinging GitHub Actions workflow_dispatch every
10-15 minutes.

Multiple shifts per day are supported. Each shift has its own hour, minute,
and shift_id. State tracks which shifts have already fired on which dates
via keys of the form "<shift_id>-YYYY-MM-DD".
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).parent
SCHEDULE_PATH = ROOT / "schedule.json"
MESSAGES_PATH = ROOT / "messages.json"
STATE_PATH = ROOT / "state.json"

PST = ZoneInfo("America/Los_Angeles")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def post_to_discord(webhook_url, message):
    resp = requests.post(
        webhook_url,
        json={"content": message},
        timeout=15,
    )
    resp.raise_for_status()
    return len(message)


def within_fire_window(now_pst, scheduled_hour, scheduled_minute, window_minutes):
    """True if now is between scheduled time and scheduled time + window."""
    scheduled = now_pst.replace(
        hour=scheduled_hour,
        minute=scheduled_minute,
        second=0,
        microsecond=0,
    )
    window_end = scheduled + timedelta(minutes=window_minutes)
    return scheduled <= now_pst <= window_end


def migrate_state(state):
    """
    Migrate legacy fired_dates (single-shift-per-day) into the new
    fired_shift_ids format. Legacy Mon-Thu were Ruby; Fri-Sun were Elijah.
    Safe to call repeatedly.
    """
    if "fired_dates" not in state:
        return
    old = state.pop("fired_dates")
    fired = set(state.get("fired_shift_ids", []))
    for date_str in old:
        try:
            y, m, d = [int(p) for p in date_str.split("-")]
        except Exception:
            continue
        weekday = datetime(y, m, d).strftime("%A").lower()
        legacy_shift = "elijah" if weekday in {"friday", "saturday", "sunday"} else "ruby"
        fired.add(f"{legacy_shift}-{date_str}")
    state["fired_shift_ids"] = sorted(fired)
    print(f"[info] Migrated {len(old)} legacy fired_dates entries to fired_shift_ids.")


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[error] DISCORD_WEBHOOK_URL not set")
        sys.exit(1)

    schedule = load_json(SCHEDULE_PATH)
    messages = load_json(MESSAGES_PATH)
    state = load_json(STATE_PATH)

    migrate_state(state)

    now_pst = datetime.now(PST)
    today_str = now_pst.strftime("%Y-%m-%d")
    weekday_name = now_pst.strftime("%A").lower()

    print(f"[info] Tick at {now_pst.isoformat()}")
    print(f"[info] weekday={weekday_name} date={today_str}")

    state["last_check"] = now_pst.isoformat()

    day_shifts = schedule.get("days", {}).get(weekday_name, [])
    if not day_shifts:
        print(f"[info] No shifts scheduled for {weekday_name}. Skipping.")
        save_json(STATE_PATH, state)
        return

    window = schedule.get("fire_window_minutes", 30)
    day_messages = messages.get(weekday_name, {})
    fired_ids = state.setdefault("fired_shift_ids", [])

    any_action = False
    for shift in day_shifts:
        hour = shift["hour"]
        minute = shift.get("minute", 0)
        shift_id = shift["shift_id"]
        fired_key = f"{shift_id}-{today_str}"

        if fired_key in fired_ids:
            print(f"[info] {shift_id}: already fired today ({fired_key}). Skipping.")
            continue

        if not within_fire_window(now_pst, hour, minute, window):
            print(
                f"[info] {shift_id}: outside fire window "
                f"({hour:02d}:{minute:02d} PST + {window}min). Skipping."
            )
            continue

        message = day_messages.get(shift_id)
        if not message:
            print(f"[warn] {shift_id}: no message defined for {weekday_name}. Skipping.")
            continue

        sent_chars = post_to_discord(webhook_url, message)
        print(f"[ok] {shift_id}: posted to Discord ({sent_chars} chars)")
        fired_ids.append(fired_key)
        any_action = True

    save_json(STATE_PATH, state)
    if not any_action:
        print("[info] Nothing fired this tick.")
    print("[info] Done.")


if __name__ == "__main__":
    main()
