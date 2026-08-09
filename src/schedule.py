from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo


SHANGHAI = ZoneInfo("Asia/Shanghai")
REPORT_DAYS = {0, 2, 4}  # Monday, Wednesday, Friday
REPORT_TIME = time(15, 0)


def latest_report_cutoff(now: datetime | None = None) -> datetime:
    if now is None:
        now = datetime.now(timezone.utc)
    local_now = now.astimezone(SHANGHAI)
    current_day_cutoff = datetime.combine(local_now.date(), REPORT_TIME, tzinfo=SHANGHAI)
    for days_back in range(8):
        candidate = current_day_cutoff - timedelta(days=days_back)
        if candidate.weekday() in REPORT_DAYS and candidate <= local_now:
            return candidate.astimezone(timezone.utc)
    raise RuntimeError("Could not determine latest report cutoff.")


def previous_report_cutoff(cutoff: datetime) -> datetime:
    local_cutoff = cutoff.astimezone(SHANGHAI)
    for days_back in range(1, 8):
        candidate = local_cutoff - timedelta(days=days_back)
        if candidate.weekday() in REPORT_DAYS:
            return candidate.astimezone(timezone.utc)
    raise RuntimeError("Could not determine previous report cutoff.")


def current_report_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    until = latest_report_cutoff(now)
    since = previous_report_cutoff(until)
    return since, until
