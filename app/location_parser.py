
import re


def extract_location(text: str) -> str:
    """Extract a place name from common natural-language requests."""

    query = text.strip()

    if not query:
        return ""

    # Remove punctuation at the end.
    query = re.sub(r"[?.!]+$", "", query).strip()

    patterns = [
        r"^(?:what(?:'s| is) the weather in)\s+(.+)$",
        r"^(?:can you show me the weather in)\s+(.+)$",
        r"^(?:show me the weather in)\s+(.+)$",
        r"^(?:weather in)\s+(.+)$",
        r"^(?:show me)\s+(.+?)\s+weather$",
        r"^(?:i want to visit)\s+(.+)$",
        r"^(?:i(?:'m| am) traveling to)\s+(.+)$",
        r"^(?:what is the temperature in)\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, query, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    # Assume the input is already a location name.
    return query
