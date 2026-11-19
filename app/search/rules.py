"""Rule-based parser: turns a question into a SearchIntent without an LLM.

It's the fallback when no model is available or a model's answer is unusable,
and the baseline that models are evaluated against. It handles two kinds of
question:

- lookups: "rain in Chicago last July", "Seattle forecast for Friday"
- discover: "sunny cities in July", "somewhere warm all year in Florida"
"""

from datetime import date
import re

from app.models import UnitSystem
from app.search.dates import MONTHS, NUMBER_WORDS, find_date
from app.search.intent import Condition, HeatmapMetric, SearchIntent, SearchMode
from app.search.states import STATE_CODES, STATE_NAMES, state_name


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

UNITS = (
    (re.compile(r"\b(fahrenheit|imperial)\b|°\s?f\b|\bdegrees f\b"), UnitSystem.imperial),
    (re.compile(r"\b(celsius|centigrade|metric)\b|°\s?c\b|\bdegrees c\b"), UnitSystem.metric),
)
PRECIPITATION = re.compile(r"\b(rain\w*|precip\w*|snow\w*|wet|drizzle|showers?|storms?)\b")
HEATMAP = re.compile(
    r"\b(heat ?map|(?:temperature|temp|rain|rainfall|precipitation|snow|weather) map|map of|maps?"
    r"|nationwide|country ?wide|all states"
    r"|across (?:the )?(?:us|u\.s\.|usa|country|nation|united states|america))\b"
)
FORECAST_WORDS = re.compile(
    r"\b(forecast|will|going to|gonna|upcoming|ahead|next|tomorrow|this week|coming"
    r"|outlook|weekend|later today|this afternoon|this evening)\b"
)
HISTORY_WORDS = re.compile(r"\b(histor\w*|was|were|ago|last|past|previous|record\w*)\b")
CURRENT_WORDS = re.compile(r"\b(now|current\w*|today|tonight|at the moment|outside)\b")
MONTH_WORDS = re.compile(r"\b(month|monthly)\b")
NATIONAL = {"us", "u.s", "u.s.", "usa", "the us", "the u.s.", "the usa", "america",
            "the united states", "united states", "the country", "country", "the nation"}

# Discover searches. The first condition word in the question wins.
CONDITIONS = [
    (Condition.sunny, r"sunn(?:y|iest|ier)|sunshine|sun|clear skies|bright"),
    (Condition.hot, r"hot(?:test|ter)?|scorching|sweltering"),
    (Condition.warm, r"warm(?:est|er)?|balmy|tropical"),
    (Condition.mild, r"mild(?:est)?|pleasant|temperate|comfortable"),
    (Condition.cool, r"cool(?:est|er)?"),
    (Condition.cold, r"cold(?:est|er)?|freezing|frigid|chilly"),
    (Condition.dry, r"dry|driest|drier|arid"),
    (Condition.rainy, r"rain(?:y|iest|ier)?|wettest|wet"),
    (Condition.snowy, r"snow(?:y|iest|ier)?|ski(?:ing)?"),
]
CONDITION_RE = [(condition, re.compile(rf"\b(?:{words})\b")) for condition, words in CONDITIONS]
# Everyday phrases that mean a condition without naming it. Checked before the
# single words above, so "escape the snow" means warm, not snowy, and "no rain"
# means dry, not rainy. The third value is the months to use if none are given.
WINTER, SUMMER = [12, 1, 2], [6, 7, 8]
CONDITION_PHRASES = [
    (Condition.warm, r"wear(?:ing)? (?:shorts|a t-?shirt|t-?shirts|sandals|flip[- ]flops)"
                     r"|(?:t-?shirt|shorts|pool) weather|beach(?: weather| days?)?", None),
    (Condition.warm, r"(?:escape|avoid|get away from|away from|out of|beat) (?:the )?"
                     r"(?:cold|snow|winter|freeze|chill)", WINTER),
    (Condition.cool, r"(?:escape|avoid|get away from|away from|out of|beat) (?:the )?"
                     r"(?:summer )?(?:heat|humidity)", SUMMER),
    (Condition.cool, r"(?:sweater|hoodie|jacket|flannel) weather", None),
    (Condition.snowy, r"white christmas", [12]),
    (Condition.snowy, r"ski(?:ing)?|snowboard(?:ing)?|build a snowman", None),
    (Condition.dry, r"(?:no|least|less|little|without|avoid(?: the)?|rarely|hardly ever|never) "
                    r"(?:rain|rains|rainy|rainfall)|stay dry|not rainy", None),
    (Condition.sunny, r"lots of (?:sun|sunshine)|blue skies?|(?:get|catch) some sun|vitamin d"
                      r"|most (?:sun|sunshine)", None),
    (Condition.mild, r"not too (?:hot|cold)|neither hot nor cold"
                     r"|(?:perfect|nice|good|great|ideal) weather", None),
]   
CONDITION_PHRASE_RE = [(condition, re.compile(rf"\b(?:{words})\b"), months)
                       for condition, words, months in CONDITION_PHRASES]
DISCOVER_CUES = re.compile(
    r"\b(somewhere|anywhere|where|which (?:city|cities|place|places|state)|cities|places"
    r"|towns|spots|destinations|locations|best place|top \d+|rank\w*)\b"
)
SEASONS = {"winter": [12, 1, 2], "spring": [3, 4, 5], "summer": [6, 7, 8],
           "fall": [9, 10, 11], "autumn": [9, 10, 11]}
YEAR_ROUND = re.compile(
    r"\b(year[- ]round|all year(?: long)?|most of the year|every month|whole year"
    r"|throughout the year|all the time|annually)\b"
)
MONTH_NAME = re.compile(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b")
MONTH_RANGE = re.compile(
    rf"\b({MONTH_NAME.pattern[3:-3]})\s+(?:through|thru|to|until|-)\s+({MONTH_NAME.pattern[3:-3]})\b"
)
LIMIT = re.compile(
    r"\b(?:top|best)\s+(\d{1,2}|" + "|".join(NUMBER_WORDS) + r")\b"
    r"|\b(\d{1,2}|" + "|".join(w for w in NUMBER_WORDS if len(w) > 2) + r")\s+(?:cities|places|towns|spots)\b"
)

# Place extraction.
PLACE_STOP = re.compile(
    r"¦|[?!;]|\b(on|during|from|between|this|next|last|tomorrow|today|yesterday|tonight"
    r"|right|now|please|weather|forecast|forecasts|temperature|temperatures|temps?"
    r"|rain|rainfall|precipitation|snow|was|is|are|were|will|be|like|been|compared?"
    r"|daily|hourly|over|across|in|for|at|by|using|show|showing|with"
    r"|get|got|feel|look|looks|early|mid|late|winter|spring|summer|fall|autumn|year)\b"
)

PLACE_PREFIX = re.compile(r"\b(?:in|for|at|near|around|over|across|of)\s+")
SUBJECT_BEFORE_KEYWORD = re.compile(
    r"^\s*(?:(?:what(?:'s| is| was)|how(?:'s| is| was)|show(?: me)?|get|give me|tell me)\s+)?"
    r"(?:the\s+)?(?P<place>[a-z][a-z .'\-]*?(?:,\s*[a-z .]+?)?)\s+"
    r"(?:weather|forecast|temperatures?|temps?|rain(?:fall)?|precipitation|conditions|climate)\b"
)
HOW_OR_SHOW = re.compile(
    r"\b(?:how\s+(?:hot|cold|warm|wet|windy|humid|rainy|snowy|nice|bad)\s+(?:was|is|will|did|does|has)"
    r"|how\s+(?:does|do)|show(?:\s+me)?(?:\s+the\s+weather\s+for)?|weather)\s+"
)
COMPARE = re.compile(r"\bcompare\s+(?P<rest>.+)")
SPLIT_PLACES = re.compile(r"\s*(?:\band\b|&|\bvs\.?|\bversus\b|\bto\b|\bwith\b)\s*")
QUESTION_WORDS = {
    "what", "what's", "whats", "how", "how's", "is", "will", "did", "does", "do", "show",
    "tell", "give", "can", "could", "would", "was", "were", "get", "find", "the", "i",
    "should", "it", "it's", "any", "when", "where", "why", "which", "please", "hot", "cold",
}
NON_PLACES = {
    "it", "there", "here", "me", "weather", "the weather", "today", "tomorrow", "now",
    "hot", "cold", "warm", "temperature", "temperatures", "forecast", "rain",
    "conditions", "average", "daily", "precipitation",
}


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_rules(query: str, today: date) -> SearchIntent:
    text = query.replace("’", "'").replace("–", "-")
    lower = text.lower()
    # A copy where recognized phrases (dates, units, ...) are blanked out with "¦",
    # so they can't be mistaken for place names. Same length, so indexes line up.
    masked = list(lower)

    def blank(start: int, end: int) -> None:
        masked[start:end] = "¦" * (end - start)

    units = None
    for pattern, unit in UNITS:
        if match := pattern.search(lower):
            units = unit
            blank(*match.span())
            break

    heatmap = HEATMAP.search(lower)
    if heatmap:
        blank(*heatmap.span())
    found = find_date(lower, today)
    if found:
        blank(found.start, found.end)
    if year_round := YEAR_ROUND.search(lower):
        blank(*year_round.span())  # "all year" isn't a place

    condition, condition_span, default_months = _find_condition(lower)
    if condition_span:
        blank(*condition_span)  # "escape the cold" isn't a place

    places = _extract_places(text, "".join(masked))
    national = [place for place in places if place.lower().strip(" .") in NATIONAL]
    places = [place for place in places if place not in national]

    if condition and _is_discover(lower, places, heatmap):
        return _discover_intent(lower, condition, places, units, today, default_months, found)

    if heatmap or national:
        return SearchIntent(
            mode=SearchMode.heatmap,
            places=[place for place in places if place.lower() in STATE_NAMES][:1],
            date=found.date if found else None,
            units=units,
            metric=HeatmapMetric.precipitation if PRECIPITATION.search(lower)
            else HeatmapMetric.temperature,
        )

    day = found.date if found else None
    month = found.month if found else None
    forecast_days = found.forecast_days if found else None
    if month and day is None:
        mode = SearchMode.monthly
    elif day is not None:
        if day < today:
            mode = SearchMode.historical
        elif day == today and not FORECAST_WORDS.search(lower):
            mode = SearchMode.current
        else:
            mode = SearchMode.forecast
    elif forecast_days or FORECAST_WORDS.search(lower):
        mode = SearchMode.forecast
    elif MONTH_WORDS.search(lower) and HISTORY_WORDS.search(lower):
        mode = SearchMode.monthly
    elif HISTORY_WORDS.search(lower) and not CURRENT_WORDS.search(lower):
        mode = SearchMode.historical
    else:
        mode = SearchMode.current

    return SearchIntent(
        mode=mode,
        places=places,
        date=day if mode is not SearchMode.current else None,
        month=month if mode is SearchMode.monthly else None,
        forecast_days=forecast_days if mode is SearchMode.forecast else None,
        units=units,
    )


# ---------------------------------------------------------------------------
# Discover searches
# ---------------------------------------------------------------------------

def _find_condition(lower: str):
    """(condition, (start, end) of a matched phrase, default months).

    Everyday phrases win over single words; otherwise the earliest word wins.
    """
    for condition, pattern, months in CONDITION_PHRASE_RE:
        if match := pattern.search(lower):
            return condition, match.span(), months
    hits = [(match.start(), match.end(), condition) for condition, pattern in CONDITION_RE
            if (match := pattern.search(lower))]
    if not hits:
        return None, None, None
    # Single words aren't blanked: "how cold did Minneapolis get" needs "cold"
    # to find the place.
    return min(hits)[2], None, None


def _is_discover(lower: str, places: list[str], heatmap) -> bool:
    """'Is it sunny in Seattle?' is a lookup; 'sunny cities in July' is discover."""
    if heatmap:
        return False
    cities = [place for place in places if state_name(place) is None]
    return bool(DISCOVER_CUES.search(lower)) or not cities


def _discover_intent(lower, condition, places, units, today, default_months=None, found=None) -> SearchIntent:
    if YEAR_ROUND.search(lower):
        months: list[int] = []
    elif match := MONTH_RANGE.search(lower):
        first, last = MONTHS[match.group(1)], MONTHS[match.group(2)]
        months = [(first - 1 + step) % 12 + 1 for step in range((last - first) % 12 + 1)]
    elif seasons := [months for name, months in SEASONS.items() if re.search(rf"\b{name}\b", lower)]:
        months = sorted({month for season in seasons for month in season})
    elif names := [name for name in MONTH_NAME.findall(lower)
                   if name != "may" or re.search(r"\b(in|during) may\b", lower)]:
        months = sorted({MONTHS[name] for name in names})
    elif found and found.date:
        months = [found.date.month]  # "warm places for Thanksgiving" -> November
    elif CURRENT_WORDS.search(lower):
        months = [today.month]
    else:
        months = default_months or []

    limit = None
    if match := LIMIT.search(lower):
        token = match.group(1) or match.group(2)
        limit = int(token) if token.isdigit() else NUMBER_WORDS[token]

    region = next((state_name(place) for place in places if state_name(place)), None)
    return SearchIntent(mode=SearchMode.discover, condition=condition, months=months,
                        region=region, limit=min(limit, 10) if limit else None, units=units)


# ---------------------------------------------------------------------------
# Place extraction
# ---------------------------------------------------------------------------

def _extract_places(text: str, masked: str) -> list[str]:
    """Pull up to three place names, keeping the user's capitalization.

    Strategies are tried in order until one finds something:
    "compare A and B", "... in/for/at PLACE", "PLACE weather",
    "how hot was PLACE", "A vs B", and a bare place at the start.
    """
    candidates: list[str] = []

    if compare := COMPARE.search(masked):
        start = compare.start("rest")
        candidates = _split_places(text, start, _cut_at_stop(masked, start))
    if not candidates:
        for match in PLACE_PREFIX.finditer(masked):
            found = _split_places(text, match.end(), _cut_at_stop(masked, match.end()))
            found = [place for place in found if place.lower() not in NON_PLACES]
            if found:
                candidates = found
                break
    if not candidates and (subject := SUBJECT_BEFORE_KEYWORD.search(masked)):
        start = subject.start("place")
        candidates = _split_places(text, start, masked[start:subject.end("place")])
    if not candidates and (verb := HOW_OR_SHOW.search(masked)):
        candidates = _split_places(text, verb.end(), _cut_at_stop(masked, verb.end()))
    if not candidates and (vs := re.search(r"(?P<a>[a-z][a-z .,']+?)\s+(?:vs\.?|versus)\s+", masked)):
        start = vs.start("a")
        candidates = _split_places(text, start, _cut_at_stop(masked, start))
    if not candidates:
        # A bare place at the start: "Portland, OR in May 2024", "Boise tomorrow",
        # or after a blanked phrase: "Mother's Day 2024 Boston".
        start = len(masked) - len(masked.lstrip("¦ "))
        segment = _cut_at_stop(masked, start)
        words = segment.split()
        if 0 < len(words) <= 4 and words[0].strip("'") not in QUESTION_WORDS:
            candidates = _split_places(text, start, segment)

    places: list[str] = []
    for candidate in candidates:
        cleaned = re.sub(r"^(?:the|city of|downtown)\s+", "", candidate.strip(" .,'\""), flags=re.I)
        cleaned = re.sub(r"\s+(?:the|a|an)$", "", cleaned, flags=re.I)
        cleaned = re.sub(r"'s$", "", cleaned)  # "Austin's forecast" -> Austin
        cleaned = " ".join(cleaned.split())
        if (not cleaned or cleaned.lower() in NON_PLACES or len(cleaned) > 60
                or cleaned.split()[0].lower() in QUESTION_WORDS):
            continue
        if cleaned.lower() not in (place.lower() for place in places):
            places.append(cleaned)
    return places[:3]


def _cut_at_stop(masked: str, start: int) -> str:
    """Text from start up to the first stop word or blanked-out phrase."""
    tail = masked[start:]
    stop = PLACE_STOP.search(tail)
    if stop is None:
        return tail
    if stop.start() == 0 and stop.group(0) != "¦":
        return ""  # a place can't start with a stop word: "in the next week"
    return tail[:stop.start()]


def _split_places(text: str, start: int, segment: str) -> list[str]:
    """Split 'Austin and Dallas' into two places, but keep 'Austin, TX' together."""
    original = text[start:start + len(segment)]
    parts, position = [], 0
    for match in SPLIT_PLACES.finditer(segment):
        parts.append(original[position:match.start()])
        position = match.end()
    parts.append(original[position:])

    places: list[str] = []
    for part in parts:
        for piece in (piece.strip() for piece in part.split(",")):
            if not piece:
                continue
            is_state = piece.lower().rstrip(".") in STATE_CODES | STATE_NAMES
            if places and is_state and "," not in places[-1]:
                places[-1] = f"{places[-1]}, {piece}"
            else:
                places.append(piece)
    return [place for place in places if re.search(r"[A-Za-z]", place)]