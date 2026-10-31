import json
import sys
from datetime import date

from festival import (
    artist_lines,
    check_new_performance,
    end_of,
    find_artist,
    festival_days,
    load_festival,
    next_after,
    on_stage_at,
    parse_day,
    parse_minutes,
    parse_moment,
    performance_id,
    programme_line,
    programme_lines,
    remove_performance,
    save_festival,
    slugify,
    venue_name_of,
)


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
    day: date = parse_day(day_text)
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
    performance = remove_performance(festival, wanted_id)
    save_festival(festival)
    print(f"Cancelled: {performance['title']}")


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