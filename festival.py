import json
import re
import unicodedata
from datetime import date, datetime, timedelta

DATA_PATH = "data/festival.json"
DAY_ENDS_AT = timedelta(hours=6)
GAP = timedelta(minutes=30)
MIN_DURATION = 1
MAX_DURATION = 360


# ---------- slugs and data ----------


def slugify(text: str) -> str:
    """'Théâtre des Planches' -> 'theatre-des-planches'."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def load_festival(path: str = DATA_PATH) -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def save_festival(festival: dict, path: str = DATA_PATH) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(festival, file, ensure_ascii=False, indent=2)


def find_venue(festival: dict, slug: str) -> dict | None:
    for venue in festival["venues"]:
        if slugify(venue["name"]) == slug:
            return venue
    return None


def find_artist(festival: dict, slug: str) -> dict | None:
    for artist in festival["artists"]:
        if slugify(artist["name"]) == slug:
            return artist
    return None


def people_of(performance: dict) -> list[tuple[str, str]]:
    """The (artist slug, role) pairs of a performance."""
    people = []
    if "artist" in performance:
        people.append((performance["artist"], "solo"))
    if "host" in performance:
        people.append((performance["host"], "host"))
    for act in performance.get("acts", []):
        people.append((act, "act"))
    if "teacher" in performance:
        people.append((performance["teacher"], "teacher"))
    return people


# ---------- objects for the API ----------


def festival_days(festival: dict) -> list[date]:
    """Every day from first_day to last_day."""
    first = date.fromisoformat(festival["first_day"])
    last = date.fromisoformat(festival["last_day"])
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]


def festival_object(festival: dict) -> dict:
    return {
        "name": festival["name"],
        "first_day": festival["first_day"],
        "last_day": festival["last_day"],
        "days": [day.isoformat() for day in festival_days(festival)],
    }


def venue_objects(festival: dict) -> list[dict]:
    return [
        {
            "slug": slugify(venue["name"]),
            "name": venue["name"],
            "capacity": venue["capacity"],
            "address": venue["address"],
        }
        for venue in festival["venues"]
    ]


def artist_objects(festival: dict) -> list[dict]:
    artists = [{"slug": slugify(a["name"]), **a} for a in festival["artists"]]
    return sorted(artists, key=lambda a: a["slug"])


# ---------- dates ----------


def start_of(performance: dict) -> datetime:
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """A festival day ends at 06:00: the day of a show is its start minus 6 hours."""
    return (start_of(performance) - DAY_ENDS_AT).date()


def venue_name_of(festival: dict, performance: dict) -> str:
    return find_venue(festival, performance["venue"])["name"]


def performance_id(performance: dict) -> str:
    return f"{performance['venue']}-{start_of(performance):%Y-%m-%d-%H%M}"


def sorted_performances(festival: dict) -> list[dict]:
    return sorted(
        festival["performances"],
        key=lambda p: (start_of(p), venue_name_of(festival, p)),
    )


def time_range(performance: dict) -> str:
    return f"{start_of(performance):%H:%M}-{end_of(performance):%H:%M}"


def full_range(performance: dict) -> str:
    return f"{start_of(performance):%Y-%m-%d %H:%M}-{end_of(performance):%H:%M}"


# ---------- parsing of what the user types ----------


def parse_day(text: str) -> date:
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a day, use YYYY-MM-DD.") from None


def parse_moment(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a moment, use YYYY-MM-DDTHH:MM.") from None


def parse_minutes(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"'{text}' is not a number of minutes.") from None


# ---------- rules ----------


def too_close(
    start1: datetime, end1: datetime, start2: datetime, end2: datetime
) -> bool:
    return start1 < end2 + GAP and start2 < end1 + GAP


def check_new_performance(festival: dict, new: dict) -> None:
    """Raise ValueError with a sentence if the new performance breaks a rule."""
    if not MIN_DURATION <= new["duration_minutes"] <= MAX_DURATION:
        raise ValueError(
            f"A duration must be between {MIN_DURATION} and {MAX_DURATION} minutes."
        )

    if new["kind"] == "solo" and not 0 <= new["min_age"] <= 18:
        raise ValueError("The minimum age of a solo show must be between 0 and 18.")

    venue = find_venue(festival, new["venue"])
    if venue is None:
        raise ValueError(f"No venue '{new['venue']}'.")

    for artist_slug, _role in people_of(new):
        if find_artist(festival, artist_slug) is None:
            raise ValueError(f"No artist '{artist_slug}'.")

    day = festival_day_of(new)
    first = date.fromisoformat(festival["first_day"])
    last = date.fromisoformat(festival["last_day"])
    if not first <= day <= last:
        raise ValueError(f"{day.isoformat()} is not a day of the festival.")

    new_start, new_end = start_of(new), end_of(new)
    for other in festival["performances"]:
        if other["venue"] == new["venue"] and too_close(
            new_start, new_end, start_of(other), end_of(other)
        ):
            raise ValueError(
                f"{venue['name']} is busy with {other['title']} ({full_range(other)}). "
                "Leave 30 minutes between two shows."
            )

    for artist_slug, _role in people_of(new):
        for other in festival["performances"]:
            if any(slug == artist_slug for slug, _ in people_of(other)) and too_close(
                new_start, new_end, start_of(other), end_of(other)
            ):
                name = find_artist(festival, artist_slug)["name"]
                raise ValueError(
                    f"{name} is on stage in {other['title']}. "
                    "Leave 30 minutes between two shows."
                )


def remove_performance(festival: dict, wanted_id: str) -> dict:
    """Remove and return the performance with this id, or raise ValueError."""
    for performance in festival["performances"]:
        if performance_id(performance) == wanted_id:
            festival["performances"].remove(performance)
            return performance
    raise ValueError(f"No performance with id '{wanted_id}'.")


# ---------- queries ----------


def programme_line(festival: dict, performance: dict) -> str:
    return (
        f"{time_range(performance)} | {venue_name_of(festival, performance)} | "
        f"{performance['title']} ({performance['kind']})"
    )


def programme_lines(festival: dict, day: date) -> list[str]:
    return [
        programme_line(festival, p)
        for p in sorted_performances(festival)
        if festival_day_of(p) == day
    ]


def artist_lines(festival: dict, slug: str) -> list[str]:
    lines = []
    for performance in sorted_performances(festival):
        for artist_slug, role in people_of(performance):
            if artist_slug == slug:
                day = festival_day_of(performance)
                lines.append(
                    f"{day:%a %d} {time_range(performance)} | "
                    f"{venue_name_of(festival, performance)} | "
                    f"{performance['title']} ({role})"
                )
    return lines


def on_stage_at(festival: dict, at: datetime) -> list[dict]:
    return [p for p in sorted_performances(festival) if start_of(p) <= at < end_of(p)]


def next_after(festival: dict, at: datetime, count: int = 3) -> list[dict]:
    return [p for p in sorted_performances(festival) if start_of(p) > at][:count]