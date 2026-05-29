#!/usr/bin/env python3
"""
Calipokehouse eBay → Discord notifier.

Time-based (no live detection): fires once per scheduled day, within a
~30 minute window after the scheduled hour. Designed to be triggered by
cron-job.org pinging GitHub Actions workflow_dispatch every 15 minutes.

State is persisted in state.json (committed back to the repo by the
workflow) so each day's notification only fires once.
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
    """
    True if now is between scheduled time and scheduled time + window_minutes
    (on the same calendar day in PST).
    """
    scheduled = now_pst.replace(
        hour=scheduled_hour,
        minute=scheduled_minute,
        second=0,
        microsecond=0,
    )
    window_end = scheduled + timedelta(minutes=window_minutes)
    return scheduled <= now_pst <= window_end


def main():
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[error] DISCORD_WEBHOOK_URL not set")
        sys.exit(1)

    schedule = load_json(SCHEDULE_PATH)
    messages = load_json(MESSAGES_PATH)
    state = load_json(STATE_PATH)

    now_pst = datetime.now(PST)
    today_str = now_pst.strftime("%Y-%m-%d")
    weekday_name = now_pst.strftime("%A").lower()  # e.g. "friday"

    print(f"[info] Tick at {now_pst.isoformat()}")
    print(f"[info] weekday={weekday_name} date={today_str}")

    # Update last_check regardless of outcome
    state["last_check"] = now_pst.isoformat()

    # Is today a scheduled day?
    day_cfg = schedule.get("days", {}).get(weekday_name)
    if not day_cfg:
        print(f"[info] No stream scheduled for {weekday_name}. Skipping.")
        save_json(STATE_PATH, state)
        return

    # Is now within the fire window?
    hour = day_cfg["hour"]
    minute = day_cfg.get("minute", 0)
    window = schedule.get("fire_window_minutes", 30)
    if not within_fire_window(now_pst, hour, minute, window):
        print(
            f"[info] Outside fire window ({hour:02d}:{minute:02d} PST + {window}min). "
            f"Skipping."
        )
        save_json(STATE_PATH, state)
        return

    # Already fired today?
    if today_str in state.get("fired_dates", []):
        print(f"[info] Already fired for {today_str}. Skipping.")
        save_json(STATE_PATH, state)
        return

    # Look up message for this weekday
    message = messages.get(weekday_name)
    if not message:
        print(f"[warn] No message defined for {weekday_name}. Skipping.")
        save_json(STATE_PATH, state)
        return

    # Fire it
    sent_chars = post_to_discord(webhook_url, message)
    print(f"[ok] Posted to Discord ({sent_chars} chars)")

    state.setdefault("fired_dates", []).append(today_str)
    save_json(STATE_PATH, state)
    print(f"[info] Marked {today_str} as fired.")
    print("[info] Done.")


if __name__ == "__main__":
    main()
