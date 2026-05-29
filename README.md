# Calipokehouse eBay → Discord Notifier

Time-based Discord notification system for Calipokehouse's eBay livestreams. Unlike the TikTok notifier (which detects when streams go live), this one just fires at a scheduled time on scheduled days — eBay doesn't expose a clean "is live" signal, and the schedule here is fixed.

## How it works

Every 15 minutes (via cron-job.org pinging GitHub's workflow_dispatch API), the script:

1. Checks today's day-of-week in PST
2. Checks if today is in `schedule.json`
3. Checks if current time is within the fire window (scheduled hour + 30 min buffer)
4. Checks `state.json` to see if today's notification already fired
5. If all clear, posts the day-specific message from `messages.json` to Discord
6. Records today's date in `state.json` so it only fires once per day

## Schedule

| Day | Time (PST) | Stream hours | Streamer |
|---|---|---|---|
| Monday | 1:00 PM | 1:00 PM – 10:00 PM | Ruby |
| Tuesday | 1:00 PM | 1:00 PM – 10:00 PM | Ruby |
| Wednesday | 1:00 PM | 1:00 PM – 10:00 PM | Ruby |
| Thursday | 1:00 PM | 1:00 PM – 10:00 PM | Ruby |
| Friday | 2:00 PM | 2:00 PM – 2:00 AM | Elijah |
| Saturday | 2:00 PM | 2:00 PM – 2:00 AM | Elijah |
| Sunday | 2:00 PM | 2:00 PM – 2:00 AM | Elijah |

Stream URL: https://www.ebay.com/ebaylive/sellers/neqbykuprsy

## Files

| File | Purpose |
|---|---|
| `notifier.py` | Main script |
| `schedule.json` | Days and times the notification should fire |
| `messages.json` | Discord messages by weekday (edit to change wording) |
| `state.json` | Auto-managed; tracks which dates have already been notified |
| `requirements.txt` | Python deps |
| `.github/workflows/notifier.yml` | GitHub Actions cron + workflow_dispatch entry point |

## Required secrets

In Settings → Secrets and variables → Actions:

| Secret | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | Discord webhook URL (same channel as Calipokehouse TikTok) |

## Required permissions

Settings → Actions → General → Workflow permissions → **Read and write permissions** (so the bot can commit updated `state.json` back).

## Maintenance

- **Edit messages:** open `messages.json` on GitHub, hit the pencil, change text, commit. Next 15-min tick uses the new wording.
- **Change days or time:** edit `schedule.json`. To add a new day, add the day in lowercase with hour/minute, plus a matching entry in `messages.json`.
- **Health check:** Actions tab should show green checkmarks roughly every 15 minutes via cron-job.org.
