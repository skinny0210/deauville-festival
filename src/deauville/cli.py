import json
import sys

from deauville.errors import FestivalError, Invalid, NotFound
from deauville.model import Festival
from deauville.parsing import parse_day, parse_minutes, parse_moment
from deauville.storage import DATA_PATH, JsonStorage, Storage


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


def add_performance(festival: Festival, storage: Storage) -> None:
    title = input("Title: ").strip()
    artist = input("Artist (slug): ").strip()
    venue = input("Venue (slug): ").strip()
    start = parse_moment(input("Start (YYYY-MM-DDTHH:MM): ").strip())
    minutes = parse_minutes(input("Duration (minutes): ").strip())

    new = festival.schedule_solo(title, artist, venue, start, minutes)
    storage.save(festival)
    print(f"Added: {new.id}")


def cancel_performance(festival: Festival, storage: Storage, wanted_id: str) -> None:
    performance = festival.remove(wanted_id)
    storage.save(festival)
    print(f"Cancelled: {performance.title}")


def serve(storage: Storage) -> None:
    import uvicorn  # only needed by this command

    from deauville.api import create_app

    uvicorn.run(create_app(storage), host="127.0.0.1", port=8000)


def print_usage() -> None:
    print("Usage: deauville [--data FILE] COMMAND")
    print("  (no command)             summary of the festival")
    print("  venues                   the venues and their seats")
    print("  programme YYYY-MM-DD     the programme of a festival day")
    print("  artist SLUG              the performances of an artist")
    print("  now YYYY-MM-DDTHH:MM     what is on stage at a moment")
    print("  add                      schedule a solo show")
    print("  cancel ID                cancel a performance")
    print("  serve                    start the website and the API")


def take_option(args: list[str], name: str, default: str) -> tuple[str, list[str]]:
    """Remove `name VALUE` from args and return (value, remaining args)."""
    if name not in args:
        return default, args
    index = args.index(name)
    if index + 1 >= len(args):
        raise Invalid(f"{name} needs a value.")
    value = args[index + 1]
    return value, args[:index] + args[index + 2 :]


def run(args: list[str], storage: Storage) -> None:
    if args == ["serve"]:
        serve(storage)
        return
    festival = storage.load()
    if not args:
        print_summary(festival)
    elif args[0] == "venues" and len(args) == 1:
        print_venues(festival)
    elif args[0] == "programme" and len(args) == 2:
        print_programme(festival, args[1])
    elif args[0] == "artist" and len(args) == 2:
        print_artist(festival, args[1])
    elif args[0] == "now" and len(args) == 2:
        print_now(festival, args[1])
    elif args[0] == "add" and len(args) == 1:
        add_performance(festival, storage)
    elif args[0] == "cancel" and len(args) == 2:
        cancel_performance(festival, storage, args[1])
    else:
        print_usage()


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        path, args = take_option(args, "--data", DATA_PATH)
        run(args, JsonStorage(path))
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
    main()