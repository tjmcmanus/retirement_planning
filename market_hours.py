"""
market_hours.py

When can a price fetched at time T no longer have changed?  Used to skip pointless refetches.

US equity prices only move between the NYSE open (9:30 ET) and close (16:00 ET) on trading days.
If prices were fetched while the market was closed *and the figures had settled*, nothing new can
exist until the next open, so a cache built then stays valid until that open instead of expiring
after a few minutes.

"Settled" is later than 16:00 on purpose: mutual-fund NAVs (many holdings here are 5-letter fund
tickers) are published some hours after the close, so a fetch at 16:30 can still return the
previous day's NAV. ``SETTLE`` is the time of day after which a fetch is treated as final.

Streamlit-free, standard library plus python-dateutil (already a dependency).
Early-close days (13:00) are treated as full days, which only means a few extra refetches.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from dateutil.easter import easter

NY = ZoneInfo("America/New_York")
OPEN = time(9, 30)
SETTLE = time(20, 0)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    d = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def _observed(d: date) -> date:
    """NYSE rule: a holiday on Saturday is observed Friday, on Sunday Monday."""
    if d.weekday() == 5:
        return d - timedelta(days=1)
    if d.weekday() == 6:
        return d + timedelta(days=1)
    return d


@lru_cache(maxsize=32)
def holidays(year: int) -> frozenset[date]:
    """NYSE full-day closures that fall in ``year``."""
    days = {
        _nth_weekday(year, 1, 0, 3),            # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),            # Presidents' Day
        easter(year) - timedelta(days=2),       # Good Friday
        _last_weekday(year, 5, 0),              # Memorial Day
        _observed(date(year, 7, 4)),            # Independence Day
        _nth_weekday(year, 9, 0, 1),            # Labor Day
        _nth_weekday(year, 11, 3, 4),           # Thanksgiving
        _observed(date(year, 12, 25)),          # Christmas
    }
    if year >= 2022:
        days.add(_observed(date(year, 6, 19)))  # Juneteenth
    new_year = date(year, 1, 1)
    if new_year.weekday() != 5:                 # a Saturday New Year is not observed on the prior Friday
        days.add(_observed(new_year))
    return frozenset(days)


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in holidays(d.year)


def _as_utc(t: datetime) -> datetime:
    """The caches store naive UTC timestamps; treat naive values as UTC."""
    return t.replace(tzinfo=timezone.utc) if t.tzinfo is None else t.astimezone(timezone.utc)


def next_open_after(t: datetime) -> datetime:
    """The first market open strictly after ``t`` (an aware datetime in New York time)."""
    d = t.date()
    while True:
        if is_trading_day(d):
            opening = datetime.combine(d, OPEN, NY)
            if opening > t:
                return opening
        d += timedelta(days=1)


def prices_final_at(t: datetime) -> bool:
    """True if a fetch made at ``t`` returned prices that cannot change before the next open."""
    t = _as_utc(t).astimezone(NY)
    if not is_trading_day(t.date()):
        return True
    return t.time() < OPEN or t.time() >= SETTLE


def prices_unchanged_since(fetched_at: datetime, now: datetime | None = None) -> bool:
    """True if nothing fetched at ``fetched_at`` can be out of date at ``now``.

    That needs two things: the fetch happened when the market was closed and settled, and no
    market open has happened since.
    """
    fetched = _as_utc(fetched_at)
    current = _as_utc(now) if now is not None else _now()
    if current < fetched or not prices_final_at(fetched):
        return False
    return current.astimezone(NY) < next_open_after(fetched.astimezone(NY))


def is_fresh(fetched_at: datetime, ttl_seconds: float, now: datetime | None = None) -> bool:
    """A cache entry is fresh while it is young, or while the market has not moved since it was made."""
    current = _as_utc(now) if now is not None else _now()
    if 0 <= (current - _as_utc(fetched_at)).total_seconds() <= ttl_seconds:
        return True
    return prices_unchanged_since(fetched_at, current)
