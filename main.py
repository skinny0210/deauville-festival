import json
import sys

from festival import (
    Festival,
    FestivalError,
    NotFound,
    load_festival,
    parse_day,
    parse_minutes,
    parse_moment,
    save_festival,
)


def print_summary(festival: Festival) -> None:
    print(festival.name)
    print(f"From {festival.first_day.isoformat()} to {festival.last_day.isoformat()}")
    print(
        f"{len(festival.venues)} venues, "
        f"{len(festival.artists)} artists, "
        f"{len(festival.performances)} performances"
    )


def print_venues(festival: Festival) -> None:
    total = 0
    for venue in festival.venues:
        print(f"{venue.slug}: {venue.name}, {venue.capacity} seats")
        total += venue.capacity
    print(f"Total: {total} seats")


def print_programme(festival: Festival, day_text: str) -> None:
    day = parse_day(day_text)
    if day not in festival.days:
        names = ", ".join(d.isoformat() for d in festival.days)
        print(f"No performance on '{day_text}'. Days: {names}")
        return
    print(f"Programme for {day:%A %d %B}:")
    for performance in festival.programme(day=day):
        print(performance.programme_line())


def print_artist(festival: Festival, slug: str) -> None:
    try:
        artist = festival.artist(slug)
    except NotFound as error:
        print(error)
        return
    print(artist.name)
    for performance, role in festival.appearances_of(artist):
        print(performance.artist_line(role))


def print_now(festival: Festival, moment_text: str) -> None:
    at = parse_moment(moment_text)
    print(f"On stage at {at:%Y-%m-%d %H:%M}:")
    for performance in festival.on_stage_at(at):
        print(
            f"- {performance.title} at {performance.venue.name}, "
            f"until {performance.end:%H:%M}"
        )
    print("Up next:")
    for performance in festival.next_after(at):
        print(f"- {performance.programme_line()}")


def add_performance(festival: Festival) -> None:
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    minutes = parse_minutes(input("Duration (minutes): ").strip())

    new = festival.schedule_solo(title, artist, venue, start, minutes)
    save_festival(festival)
    print(f"Added: {new.id}")


def cancel_performance(festival: Festival, wanted_id: str) -> None:
    performance = festival.remove(wanted_id)
    save_festival(festival)
    print(f"Cancelled: {performance.title}")


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
    except (FestivalError, KeyError) as error:
        print(f"Error: {error}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv)