import re
import unicodedata
from datetime import date, datetime

from deauville.errors import Invalid


def slugify(text: str) -> str:
    """'Théâtre des Planches' -> 'theatre-des-planches'."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def clean_name(value: str, what: str) -> str:
    name = value.strip()
    if not name:
        raise Invalid(f"A {what} name cannot be empty.")
    return name


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise Invalid(f"'{text}' is not a day, use YYYY-MM-DD.") from None


def parse_moment(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise Invalid(f"'{text}' is not a moment, use YYYY-MM-DDTHH:MM.") from None


def parse_minutes(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise Invalid(f"'{text}' is not a number of minutes.") from None
