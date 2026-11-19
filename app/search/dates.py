"""Find the first date phrase in a question and turn it into concrete values.

Each rule is a regular expression plus a small function that converts the
match into a DateMatch. Rules are tried in order, so more specific patterns
("the day after tomorrow") come before shorter ones ("tomorrow").
"""

from calendar import monthrange
from dataclasses import dataclass
import datetime
from datetime import date, timedelta
import re
from typing import Callable


MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9, "october": 10,
    "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
HOLIDAYS = {
    "christmas eve": (12, 24), "christmas day": (12, 25), "christmas": (12, 25),
    "new year's eve": (12, 31), "new years eve": (12, 31),
    "new year's day": (1, 1), "new years day": (1, 1), "halloween": (10, 31),
    "independence day": (7, 4), "fourth of july": (7, 4), "4th of july": (7, 4),
    "july 4th": (7, 4), "valentine's day": (2, 14), "valentines day": (2, 14),
}
# Holidays on "the Nth weekday of a month": (month, weekday 0=Monday, N; -1 = last).
MOVING_HOLIDAYS = {
    "thanksgiving": (11, 3, 4), "thanksgiving day": (11, 3, 4),
    "memorial day": (5, 0, -1), "labor day": (9, 0, 1),
    "mlk day": (1, 0, 3), "martin luther king day": (1, 0, 3),
    "martin luther king jr day": (1, 0, 3),
    "presidents day": (2, 0, 3), "presidents' day": (2, 0, 3), "president's day": (2, 0, 3),
    "mother's day": (5, 6, 2), "mothers day": (5, 6, 2),
    "father's day": (6, 6, 3), "fathers day": (6, 6, 3),
}
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "fourteen": 14, "fifteen": 15,
    "sixteen": 16,
}


def _alternatives(words) -> str:
    """Regex alternation with longest words first, so 'sept' wins over 'sep'."""
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


MONTH = _alternatives(MONTHS)
WEEKDAY = _alternatives(WEEKDAYS)
HOLIDAY = _alternatives(HOLIDAYS)
MOVING_HOLIDAY = _alternatives(MOVING_HOLIDAYS)
NUMBER = r"\d{1,2}|" + _alternatives(NUMBER_WORDS)


@dataclass
class DateMatch:
    start: int
    end: int
    date: datetime.date | None = None  # see intent.py for why not plain `date`
    month: str | None = None          # "YYYY-MM", a specific past month
    forecast_days: int | None = None


def find_date(lower: str, today: date) -> DateMatch | None:
    """Return the first date phrase in the (lowercased) question, or None."""
    for pattern, convert in RULES:
        match = re.search(pattern, lower)
        if match:
            values = convert(match.groups(), today, match.group(0))
            if values:
                return DateMatch(match.start(), match.end(), **values)
    return None


# Converters: (regex groups, today, matched text) -> fields for DateMatch, or None.

def _iso(g, today, text):
    return _day(_safe_date(int(g[0]), int(g[1]), int(g[2])))


def _us_numeric(g, today, text):
    year = int(g[2])
    if year < 100:
        year += 2000 if year < 50 else 1900
    return _day(_safe_date(year, int(g[0]), int(g[1])))


def _holiday(g, today, text):
    month, day = HOLIDAYS[g[0]]
    return _day(_safe_date(int(g[1]), month, day) if g[1] else _nearest_year(today, month, day))

def _moving_holiday(g, today, text):
    month, weekday, n = MOVING_HOLIDAYS[g[0]]
    if g[1]:
        return _day(nth_weekday(int(g[1]), month, weekday, n))
    # No year: this year's, unless that's beyond the forecast range.
    candidate = nth_weekday(today.year, month, weekday, n)
    if candidate > today + timedelta(days=15):
        candidate = nth_weekday(today.year - 1, month, weekday, n)
    return _day(candidate)


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth weekday of a month (n=-1 for the last): Thanksgiving is (11, 3, 4)."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year, month, monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)

def _month_day(g, today, text):
    if g[0] == "may" and not re.search(r"may\s+\d", text):
        return None  # "may" as in "it may rain"
    month, day = MONTHS[g[0]], int(g[1])
    return _day(_safe_date(int(g[2]), month, day) if g[2] else _nearest_year(today, month, day))


def _day_month(g, today, text):
    month, day = MONTHS[g[1]], int(g[0])
    return _day(_safe_date(int(g[2]), month, day) if g[2] else _nearest_year(today, month, day))


def _month_year(g, today, text):
    return {"month": f"{int(g[1]):04d}-{MONTHS[g[0]]:02d}"}


def _last_named_month(g, today, text):
    """'last July' / 'in July': the most recent July (this month counts for 'in')."""
    month = MONTHS[g[0]]
    if month == today.month and not text.startswith(("last", "this past", "past")):
        return {"month": f"{today:%Y-%m}"}
    year = today.year if month < today.month else today.year - 1
    return {"month": f"{year:04d}-{month:02d}"}


def _last_month(g, today, text):
    return {"month": f"{today.replace(day=1) - timedelta(days=1):%Y-%m}"}


def _this_month(g, today, text):
    return {"month": f"{today:%Y-%m}"}


def _offset(days):
    return lambda g, today, text: _day(today + timedelta(days=days))


def _ago(g, today, text):
    amount, unit = _number(g[0]), g[1]
    if unit == "day":
        return _day(today - timedelta(days=amount))
    if unit == "week":
        return _day(today - timedelta(weeks=amount))
    if unit == "month":
        start = today.replace(day=1)
        for _ in range(amount):
            start = (start - timedelta(days=1)).replace(day=1)
        return {"month": f"{start:%Y-%m}"}
    return _day(_safe_date(today.year - amount, today.month, today.day))


def _from_now(g, today, text):
    amount = _number(g[0])
    return _day(today + timedelta(days=amount * (7 if g[1] == "week" else 1)))


def _next_days(g, today, text):
    return {"forecast_days": min(max(_number(g[0]), 1), 16)}


def _week_ahead(g, today, text):
    return {"forecast_days": 7}


def _weekend(g, today, text):
    # On a Saturday or Sunday, "this weekend" is already here.
    days = 0 if today.weekday() >= 5 else 5 - today.weekday()
    if text.startswith("next"):
        days += 7
    return _day(today + timedelta(days=days))


def _weekday(g, today, text):
    qualifier, target = g[0], WEEKDAYS.index(g[1])
    if qualifier in ("last", "this past"):
        return _day(today - timedelta(days=(today.weekday() - target) % 7 or 7))
    days = (target - today.weekday()) % 7
    if qualifier == "next" and days == 0:
        days = 7
    return _day(today + timedelta(days=days))


RULES: list[tuple[str, Callable]] = [
    (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", _iso),
    (r"\b(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})\b", _us_numeric),
    (rf"\b({HOLIDAY})(?:,?\s+(?:of\s+)?(\d{{4}}))?", _holiday),
    (rf"\b({MONTH})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", _month_day),
    (rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({MONTH})\b\.?(?:,?\s+(\d{{4}}))?", _day_month),
    (rf"\b({MONTH})\.?\s+(?:of\s+)?(\d{{4}})\b", _month_year),
    (rf"\b(?:last|this past|past)\s+({MONTH})\b", _last_named_month),
    (r"\b(?:last|previous|past) month\b", _last_month),
    (r"\bthis month\b", _this_month),
    (r"\bday after tomorrow\b", _offset(2)),
    (r"\btomorrow\b", _offset(1)),
    (r"\byesterday\b", _offset(-1)),
    (rf"\b({NUMBER})\s+(day|week|month|year)s?\s+ago\b", _ago),
    (rf"\b({NUMBER})\s+(day|week)s?\s+from (?:now|today)\b", _from_now),
    (r"\b(?:later today|this afternoon|this evening)\b", _offset(0)),
    (r"\b(?:today|tonight|right now|currently|at the moment)\b", _offset(0)),
    (r"\b(?:last|past|previous) week\b", _offset(-7)),
    (rf"\b(?:next|coming|upcoming)\s+({NUMBER})\s+days?\b", _next_days),
    (r"\b(\d{1,2})[- ]day\b", _next_days),
    (r"\b(?:this week|next week|week ahead|coming week|the week|7 days)\b", _week_ahead),
    (r"\b(?:this|next|the|coming) weekend\b", _weekend),
    (rf"\b(last|this past|this|next|on|coming)?\s*({WEEKDAY})\b", _weekday),
    (rf"\b(?:in|during|of|for)\s+({MONTH})\b", _last_named_month),
    (rf"\b({MOVING_HOLIDAY})(?:,?\s+(?:of\s+)?(\d{{4}}))?", _moving_holiday),
    (rf"\b({HOLIDAY})(?:,?\s+(?:of\s+)?(\d{{4}}))?", _holiday),
]


def _day(value: date | None) -> dict | None:
    return {"date": value} if value else None


def _nearest_year(today: date, month: int, day: int) -> date | None:
    """A date without a year: this year, unless that's beyond the forecast range."""
    candidate = _safe_date(today.year, month, day)
    if candidate and candidate > today + timedelta(days=15):
        candidate = _safe_date(today.year - 1, month, day)
    return candidate


def _number(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


def _safe_date(year: int, month: int, day: int) -> date | None:
    """Build a date, clamping Feb 30 to Feb 28/29 and rejecting nonsense."""
    if not 1 <= month <= 12 or day < 1:
        return None
    return date(year, month, min(day, monthrange(year, month)[1]))