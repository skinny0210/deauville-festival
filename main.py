import json
import re
import sys
import unicodedata
from datetime import date, datetime, timedelta

DAY_ENDS_AT = timedelta(hours=6)


def slugify(text: str) -> str:
    """'Théâtre des Planches' -> 'theatre-des-planches'."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def load_festival(path: str = "data/festival.json") -> dict:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


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


def start_of(performance: dict) -> datetime:
    return datetime.fromisoformat(performance["start"])


def end_of(performance: dict) -> datetime:
    return start_of(performance) + timedelta(minutes=performance["duration_minutes"])


def festival_day_of(performance: dict) -> date:
    """A festival day ends at 06:00: the day of a show is its start minus 6 hours."""
    return (start_of(performance) - DAY_ENDS_AT).date()


def venue_name_of(festival: dict, performance: dict) -> str:
    return find_venue(festival, performance["venue"])["name"]


def sorted_performances(festival: dict) -> list[dict]:
    return sorted(
        festival["performances"],
        key=lambda p: (start_of(p), venue_name_of(festival, p)),
    )


def festival_days(festival: dict) -> list[date]:
    return sorted({festival_day_of(p) for p in festival["performances"]})


def time_range(performance: dict) -> str:
    return f"{start_of(performance):%H:%M}-{end_of(performance):%H:%M}"


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
    return [
        p for p in sorted_performances(festival) if start_of(p) <= at < end_of(p)
    ]


def next_after(festival: dict, at: datetime, count: int = 3) -> list[dict]:
    return [p for p in sorted_performances(festival) if start_of(p) > at][:count]


def print_summary(festival: dict) -> None:
    print(festival["name"])
    print(f"From {festival['first_day']} to {festival['last_day']}")
    print(
        f"{len(festival['venues'])} venues, "
        f"{len(festival['artists'])} artists, "
        f"{len(festival['performances'])} performances"
    )


def print_venues(festival: dict) -> None:
    total = 0
    for venue in festival["venues"]:
        print(f"{slugify(venue['name'])}: {venue['name']}, {venue['capacity']} seats")
        total += venue["capacity"]
    print(f"Total: {total} seats")


def print_programme(festival: dict, day_text: str) -> None:
    day = date.fromisoformat(day_text)
    days = festival_days(festival)
    if day not in days:
        names = ", ".join(d.isoformat() for d in days)
        print(f"No performance on '{day_text}'. Days: {names}")
        return
    print(f"Programme for {day:%A %d %B}:")
    for line in programme_lines(festival, day):
        print(line)


def print_artist(festival: dict, slug: str) -> None:
    artist = find_artist(festival, slug)
    if artist is None:
        print(f"No artist '{slug}'.")
        return
    print(artist["name"])
    for line in artist_lines(festival, slug):
        print(line)


def print_now(festival: dict, moment_text: str) -> None:
    at = datetime.fromisoformat(moment_text)
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    for performance in on_stage_at(festival, at):
        print(
            f"- {performance['title']} at {venue_name_of(festival, performance)}, "
            f"until {end_of(performance):%H:%M}"
        )
    print("Up next:")
    for performance in next_after(festival, at):
        print(f"- {programme_line(festival, performance)}")


def print_usage() -> None:
    print("Usage:")
    print("  uv run main.py                        summary of the festival")
    print("  uv run main.py venues                 the venues and their seats")
    print("  uv run main.py programme YYYY-MM-DD   the programme of a festival day")
    print("  uv run main.py artist SLUG            the performances of an artist")
    print("  uv run main.py now YYYY-MM-DDTHH:MM   what is on stage at a moment")


def main(argv: list[str]) -> None:
    festival = load_festival()
    if len(argv) == 1:
        print_summary(festival)
    elif argv[1] == "venues" and len(argv) == 2:
        print_venues(festival)
    elif argv[1] == "programme" and len(argv) == 3:
        print_programme(festival, argv[2])
    elif argv[1] == "artist" and len(argv) == 3:
        print_artist(festival, argv[2])
    elif argv[1] == "now" and len(argv) == 3:
        print_now(festival, argv[2])
    else:
        print_usage()


if __name__ == "__main__":
    main(sys.argv)