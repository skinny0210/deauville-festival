import json
import re
import sys
import unicodedata


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


def sorted_performances(festival: dict) -> list[dict]:
    return sorted(
        festival["performances"],
        key=lambda p: (p["start"], find_venue(festival, p["venue"])["name"]),
    )


def festival_days(festival: dict) -> list[str]:
    return sorted({p["start"][:10] for p in festival["performances"]})


def programme_lines(festival: dict, day: str) -> list[str]:
    lines = []
    for performance in sorted_performances(festival):
        if performance["start"][:10] == day:
            time = performance["start"][11:]
            venue = find_venue(festival, performance["venue"])["name"]
            lines.append(
                f"{time} | {venue} | {performance['title']} ({performance['kind']})"
            )
    return lines


def artist_lines(festival: dict, slug: str) -> list[str]:
    lines = []
    for performance in sorted_performances(festival):
        for artist_slug, role in people_of(performance):
            if artist_slug == slug:
                start = performance["start"].replace("T", " ")
                venue = find_venue(festival, performance["venue"])["name"]
                lines.append(f"{start} | {venue} | {performance['title']} ({role})")
    return lines


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


def print_programme(festival: dict, day: str) -> None:
    if day not in festival_days(festival):
        print(f"No performance on '{day}'. Days: {', '.join(festival_days(festival))}")
        return
    print(f"Programme for {day}:")
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


def print_usage() -> None:
    print("Usage:")
    print("  uv run main.py                        summary of the festival")
    print("  uv run main.py venues                 the venues and their seats")
    print("  uv run main.py programme YYYY-MM-DD   the programme of a day")
    print("  uv run main.py artist SLUG            the performances of an artist")


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
    else:
        print_usage()


if __name__ == "__main__":
    main(sys.argv)