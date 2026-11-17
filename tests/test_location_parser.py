
import pytest

from app.location_parser import extract_location


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Austin", "Austin"),
        ("What's the weather in Austin?", "Austin"),
        ("Show me Seattle weather", "Seattle"),
        ("I want to visit Denver", "Denver"),
        ("Weather in College Station, Texas", "College Station, Texas"),
        ("Can you show me the weather in Boston?", "Boston"),
        ("I'm traveling to Chicago", "Chicago"),
        ("What is the temperature in Miami?", "Miami"),
        ("  Seattle  ", "Seattle"),
        ("", ""),
    ],
)
def test_extract_location(text: str, expected: str) -> None:
    assert extract_location(text) == expected
