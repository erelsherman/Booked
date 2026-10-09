"""Who may use the server, and how much they may spend.

Every scan spends API money, so the server enforces four limits before it calls the model:
a per-person daily photo limit, a total daily photo limit, a total daily spend and a monthly spend.
Usage is kept in a small SQLite file so a restart does not reset the counters, provided the file lives
on storage that survives restarts (see docs/DEPLOY.md: the free Render tier wipes it, which is why
the monthly limit in the Anthropic Console is the limit that really matters).
"""

from __future__ import annotations

import secrets
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def parse_invites(raw: str) -> dict[str, str]:
    """'anna=x7k2,ben=p9q4' -> {'x7k2': 'anna', 'p9q4': 'ben'}. A bare 'code' gets the name 'guest-' plus its first 4 characters."""
    out: dict[str, str] = {}
    for part in (p.strip() for p in raw.split(",")):
        if not part:
            continue
        name, sep, code = part.partition("=")
        if not sep:
            name, code = f"guest-{part[:4]}", part
        out[code.strip()] = name.strip()
    return out


@dataclass(frozen=True)
class Caps:
    per_person_photos_per_day: int = 12
    total_photos_per_day: int = 60
    total_usd_per_day: float = 1.0
    total_usd_per_month: float = 5.0


class LimitReached(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class Ledger:
    """Thread-safe usage counters, per UTC day and person."""

    def __init__(self, path: str | Path | None, caps: Caps) -> None:
        self.caps = caps
        self._lock = threading.Lock()
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path) if path else ":memory:", check_same_thread=False)
        self._db.execute("create table if not exists usage (day text, who text, photos integer, usd real, primary key (day, who))")
        self._db.commit()

    @staticmethod
    def _day() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _sum(self, column: str, where: str, args: tuple) -> float:
        row = self._db.execute(f"select coalesce(sum({column}), 0) from usage where {where}", args).fetchone()
        return float(row[0])

    def reserve(self, who: str, photos: int) -> None:
        """Count the photos before the paid call; raises LimitReached with a message fit to show the user."""
        day = self._day()
        with self._lock:
            mine = self._sum("photos", "day = ? and who = ?", (day, who))
            if mine + photos > self.caps.per_person_photos_per_day:
                left = max(0, int(self.caps.per_person_photos_per_day - mine))
                raise LimitReached(f"That is your daily limit of {self.caps.per_person_photos_per_day} photos ({left} left today). It resets at midnight UTC.")
            if self._sum("photos", "day = ?", (day,)) + photos > self.caps.total_photos_per_day:
                raise LimitReached("The app has reached its daily scanning limit. Please try again tomorrow.")
            if self._sum("usd", "day = ?", (day,)) >= self.caps.total_usd_per_day:
                raise LimitReached("The app has reached its daily spending cap. Please try again tomorrow.")
            if self._sum("usd", "day like ?", (day[:7] + "%",)) >= self.caps.total_usd_per_month:
                raise LimitReached("The app has reached its monthly spending cap.")
            self._add(day, who, photos, 0.0)

    def record_cost(self, who: str, usd: float) -> None:
        with self._lock:
            self._add(self._day(), who, 0, usd)

    def refund(self, who: str, photos: int) -> None:
        """Give photos back when the paid call never happened (for example a rejected upload)."""
        with self._lock:
            self._add(self._day(), who, -photos, 0.0)

    def _add(self, day: str, who: str, photos: int, usd: float) -> None:
        self._db.execute(
            "insert into usage (day, who, photos, usd) values (?, ?, ?, ?) "
            "on conflict(day, who) do update set photos = photos + excluded.photos, usd = usd + excluded.usd",
            (day, who, photos, usd),
        )
        self._db.commit()

    def today(self, who: str) -> dict:
        day = self._day()
        with self._lock:
            return {
                "photos_left_today": max(0, int(self.caps.per_person_photos_per_day - self._sum("photos", "day = ? and who = ?", (day, who)))),
                "spent_today_usd": round(self._sum("usd", "day = ?", (day,)), 4),
                "spent_month_usd": round(self._sum("usd", "day like ?", (day[:7] + "%",)), 4),
            }


def who_is(presented: str, access_token: str, invites: dict[str, str]) -> str | None:
    """Name of the person a code belongs to, or None. Compares in constant time."""
    for code, name in invites.items():
        if secrets.compare_digest(presented, code):
            return name
    if access_token and secrets.compare_digest(presented, access_token):
        return "owner"
    return None
