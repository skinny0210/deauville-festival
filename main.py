import json
import re
import sys
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


def festival_days(festival: dict) -> list[date]:
    return sorted({festival_day_of(p) for p in festival["performances"]})


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


# ---------- commands ----------


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
    day = parse_day(day_text)
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
    at = parse_moment(moment_text)
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    for performance in on_stage_at(festival, at):
        print(
            f"- {performance['title']} at {venue_name_of(festival, performance)}, "
            f"until {end_of(performance):%H:%M}"
        )
    print("Up next:")
    for performance in next_after(festival, at):
        print(f"- {programme_line(festival, performance)}")


def add_performance(festival: dict) -> None:
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    minutes = parse_minutes(input("Duration (minutes): ").strip())

    new = {
        "kind": "solo",
        "title": title,
        "venue": venue,
        "start": start.strftime("%Y-%m-%dT%H:%M"),
        "duration_minutes": minutes,
        "description": "",
        "artist": artist,
        "min_age": 0,
    }
    check_new_performance(festival, new)
    festival["performances"].append(new)
    save_festival(festival)
    print(f"Added: {performance_id(new)}")


def cancel_performance(festival: dict, wanted_id: str) -> None:
    for performance in festival["performances"]:
        if performance_id(performance) == wanted_id:
            festival["performances"].remove(performance)
            save_festival(festival)
            print(f"Cancelled: {performance['title']}")
            return
    raise ValueError(f"No performance with id '{wanted_id}'.")


def print_usage() -> None:
    print("Usage:")
    print("  uv run main.py                        summary of the festival")
    print("  uv run main.py venues                 the venues and their seats")
    print("  uv run main.py programme YYYY-MM-DD   the programme of a festival day")
    print("  uv run main.py artist SLUG            the performances of an artist")
    print("  uv run main.py now YYYY-MM-DDTHH:MM   what is on stage at a moment")
    print("  uv run main.py add                    schedule a solo show")
    print("  uv run main.py cancel ID              cancel a performance")


def run(argv: list[str]) -> None:
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
    elif argv[1] == "add" and len(argv) == 2:
        add_performance(festival)
    elif argv[1] == "cancel" and len(argv) == 3:
        cancel_performance(festival, argv[2])
    else:
        print_usage()


def main(argv: list[str]) -> None:
    try:
        run(argv)
    except FileNotFoundError as error:
        print(f"Error: file not found: {error.filename}.")
        sys.exit(1)
    except json.JSONDecodeError as error:
        print(f"Error: the data file is damaged ({error}).")
        sys.exit(1)
    except (ValueError, KeyError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)