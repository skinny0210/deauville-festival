import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

DATA_PATH = "data/festival.json"
DAY_ENDS_AT = timedelta(hours=6)
GAP = timedelta(minutes=30)
MIN_DURATION = 1
MAX_DURATION = 360
KINDS = ("solo", "lineup", "workshop")
STAMP = "%Y-%m-%dT%H:%M"


class NotFound(ValueError):
    """A slug or an id that does not exist."""


# ---------- helpers ----------


def slugify(text: str) -> str:
    """'Théâtre des Planches' -> 'theatre-des-planches'."""
    ascii_text = (
        unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def clean_name(value: str, what: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError(f"A {what} name cannot be empty.")
    return name


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


# ---------- classes ----------


@dataclass
class Venue:
    name: str
    capacity: int
    address: str

    def __post_init__(self) -> None:
        self.name = clean_name(self.name, "venue")
        if self.capacity < 1:
            raise ValueError(f"{self.name} needs at least 1 seat.")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }

    def to_data(self) -> dict:
        return {"name": self.name, "capacity": self.capacity, "address": self.address}


@dataclass
class Artist:
    name: str
    bio: str = ""
    photo_url: str = ""

    def __post_init__(self) -> None:
        self.name = clean_name(self.name, "artist")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def short_view(self) -> dict:
        return {"slug": self.slug, "name": self.name}

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "bio": self.bio,
            "photo_url": self.photo_url,
        }

    def to_data(self) -> dict:
        return {"name": self.name, "bio": self.bio, "photo_url": self.photo_url}


@dataclass
class Performance:
    kind: str
    title: str
    venue: Venue
    start: datetime
    duration_minutes: int
    description: str = ""
    # solo
    artist: Artist | None = None
    min_age: int | None = None
    # lineup
    host: Artist | None = None
    acts: list[Artist] = field(default_factory=list)
    # workshop
    teacher: Artist | None = None
    max_participants: int | None = None
    participants: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.title = clean_name(self.title, "performance")
        if self.kind not in KINDS:
            raise ValueError(f"'{self.kind}' is not a kind of performance.")

    # computed from the data
    @property
    def end(self) -> datetime:
        return self.start + timedelta(minutes=self.duration_minutes)

    @property
    def festival_day(self) -> date:
        """A festival day ends at 06:00: start minus 6 hours."""
        return (self.start - DAY_ENDS_AT).date()

    @property
    def id(self) -> str:
        return f"{self.venue.slug}-{self.start:%Y-%m-%d-%H%M}"

    @property
    def capacity(self) -> int:
        return self.venue.capacity

    @property
    def places_left(self) -> int | None:
        if self.kind != "workshop":
            return None
        places = min(self.max_participants, self.venue.capacity)
        return places - len(self.participants)

    @property
    def people(self) -> list[tuple[Artist, str]]:
        """The (artist, role) pairs on stage."""
        pairs = []
        if self.kind == "solo":
            pairs.append((self.artist, "solo"))
        elif self.kind == "lineup":
            pairs.append((self.host, "host"))
            pairs.extend((act, "act") for act in self.acts)
        else:
            pairs.append((self.teacher, "teacher"))
        return pairs

    @property
    def summary(self) -> str:
        if self.kind == "solo":
            return f"{self.artist.name}, ages {self.min_age}+"
        if self.kind == "lineup":
            acts = ", ".join(act.name for act in self.acts)
            return f"hosted by {self.host.name}, with {acts}"
        return f"workshop with {self.teacher.name}"

    # questions
    def involves(self, artist: Artist) -> bool:
        return any(person.slug == artist.slug for person, _ in self.people)

    def role_of(self, artist: Artist) -> str:
        for person, role in self.people:
            if person.slug == artist.slug:
                return role
        raise ValueError(f"{artist.name} is not on stage in {self.title}.")

    def clashes_with(self, other: "Performance", gap: timedelta = GAP) -> bool:
        return self.start < other.end + gap and other.start < self.end + gap

    # display
    def time_range(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M}"

    def full_range(self) -> str:
        return f"{self.start:%Y-%m-%d %H:%M}-{self.end:%H:%M}"

    def programme_line(self) -> str:
        return f"{self.time_range()} | {self.venue.name} | {self.title} ({self.kind})"

    def artist_line(self, role: str) -> str:
        return (
            f"{self.festival_day:%a %d} {self.time_range()} | "
            f"{self.venue.name} | {self.title} ({role})"
        )

    # conversions
    def to_view(self) -> dict:
        view = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "venue_name": self.venue.name,
            "start": self.start.strftime(STAMP),
            "end": self.end.strftime(STAMP),
            "duration_minutes": self.duration_minutes,
            "festival_day": self.festival_day.isoformat(),
            "description": self.description,
            "summary": self.summary,
            "capacity": self.capacity,
            "artists": [person.short_view() for person, _ in self.people],
        }
        if self.kind == "solo":
            view["artist"] = self.artist.slug
            view["min_age"] = self.min_age
        elif self.kind == "lineup":
            view["host"] = self.host.slug
            view["acts"] = [act.slug for act in self.acts]
        else:
            view["teacher"] = self.teacher.slug
            view["max_participants"] = self.max_participants
            view["participants"] = list(self.participants)
            view["places_left"] = self.places_left
        return view

    def to_data(self) -> dict:
        data = {
            "kind": self.kind,
            "title": self.title,
            "venue": self.venue.slug,
            "start": self.start.strftime(STAMP),
            "duration_minutes": self.duration_minutes,
            "description": self.description,
        }
        if self.kind == "solo":
            data["artist"] = self.artist.slug
            data["min_age"] = self.min_age
        elif self.kind == "lineup":
            data["host"] = self.host.slug
            data["acts"] = [act.slug for act in self.acts]
        else:
            data["teacher"] = self.teacher.slug
            data["max_participants"] = self.max_participants
            data["participants"] = list(self.participants)
        return data


class Festival:
    def __init__(
        self,
        name: str,
        first_day: date,
        last_day: date,
        venues: list[Venue],
        artists: list[Artist],
    ) -> None:
        self.name = name
        self.first_day = first_day
        self.last_day = last_day
        self.venues = venues
        self.artists = artists
        self.performances: list[Performance] = []

    # building from the file
    @classmethod
    def from_data(cls, data: dict) -> "Festival":
        festival = cls(
            data["name"],
            date.fromisoformat(data["first_day"]),
            date.fromisoformat(data["last_day"]),
            [Venue(v["name"], v["capacity"], v["address"]) for v in data["venues"]],
            [
                Artist(a["name"], a.get("bio", ""), a.get("photo_url", ""))
                for a in data["artists"]
            ],
        )
        for item in data["performances"]:
            festival.performances.append(festival._build(item))
        return festival

    def _build(self, item: dict) -> Performance:
        performance = Performance(
            kind=item["kind"],
            title=item["title"],
            venue=self.venue(item["venue"]),
            start=datetime.fromisoformat(item["start"]),
            duration_minutes=item["duration_minutes"],
            description=item.get("description", ""),
        )
        if performance.kind == "solo":
            performance.artist = self.artist(item["artist"])
            performance.min_age = item["min_age"]
        elif performance.kind == "lineup":
            performance.host = self.artist(item["host"])
            performance.acts = [self.artist(slug) for slug in item["acts"]]
        else:
            performance.teacher = self.artist(item["teacher"])
            performance.max_participants = item["max_participants"]
            performance.participants = list(item["participants"])
        return performance

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [v.to_data() for v in self.venues],
            "artists": [a.to_data() for a in self.artists],
            "performances": [p.to_data() for p in self.performances],
        }

    def to_view(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "days": [day.isoformat() for day in self.days],
        }

    # finding
    @property
    def days(self) -> list[date]:
        count = (self.last_day - self.first_day).days + 1
        return [self.first_day + timedelta(days=i) for i in range(count)]

    def venue(self, slug: str) -> Venue:
        for venue in self.venues:
            if venue.slug == slug:
                return venue
        raise NotFound(f"No venue '{slug}'.")

    def artist(self, slug: str) -> Artist:
        for artist in self.artists:
            if artist.slug == slug:
                return artist
        raise NotFound(f"No artist '{slug}'.")

    def performance(self, performance_id: str) -> Performance:
        for performance in self.performances:
            if performance.id == performance_id:
                return performance
        raise NotFound(f"No performance with id '{performance_id}'.")

    def artists_sorted(self) -> list[Artist]:
        return sorted(self.artists, key=lambda a: a.slug)

    def sorted_performances(self) -> list[Performance]:
        return sorted(self.performances, key=lambda p: (p.start, p.venue.name))

    def programme(
        self, day: date | None = None, venue_slug: str | None = None
    ) -> list[Performance]:
        if venue_slug is not None:
            self.venue(venue_slug)  # raises NotFound if unknown
        return [
            p
            for p in self.sorted_performances()
            if (day is None or p.festival_day == day)
            and (venue_slug is None or p.venue.slug == venue_slug)
        ]

    def appearances_of(self, artist: Artist) -> list[tuple[Performance, str]]:
        return [
            (p, p.role_of(artist))
            for p in self.sorted_performances()
            if p.involves(artist)
        ]

    def on_stage_at(self, at: datetime) -> list[Performance]:
        return [p for p in self.sorted_performances() if p.start <= at < p.end]

    def next_after(self, at: datetime, count: int = 3) -> list[Performance]:
        return [p for p in self.sorted_performances() if p.start > at][:count]

    # rules
    def check(self, new: Performance) -> None:
        """Raise ValueError with a sentence if `new` breaks a rule."""
        if not MIN_DURATION <= new.duration_minutes <= MAX_DURATION:
            raise ValueError(
                f"A duration must be between {MIN_DURATION} and {MAX_DURATION} minutes."
            )
        if new.kind == "solo" and not 0 <= new.min_age <= 18:
            raise ValueError("The minimum age of a solo show must be between 0 and 18.")
        if not self.first_day <= new.festival_day <= self.last_day:
            raise ValueError(f"{new.festival_day.isoformat()} is not a day of the festival.")

        for other in self.performances:
            if other.venue.slug == new.venue.slug and new.clashes_with(other):
                raise ValueError(
                    f"{new.venue.name} is busy with {other.title} ({other.full_range()}). "
                    "Leave 30 minutes between two shows."
                )
        for artist, _role in new.people:
            for other in self.performances:
                if other.involves(artist) and new.clashes_with(other):
                    raise ValueError(
                        f"{artist.name} is on stage in {other.title}. "
                        "Leave 30 minutes between two shows."
                    )

    def schedule_solo(
        self,
        title: str,
        artist_slug: str,
        venue_slug: str,
        start: datetime,
        minutes: int,
        min_age: int = 0,
    ) -> Performance:
        new = Performance(
            kind="solo",
            title=title,
            venue=self.venue(venue_slug),
            start=start,
            duration_minutes=minutes,
            artist=self.artist(artist_slug),
            min_age=min_age,
        )
        self.check(new)
        self.performances.append(new)
        return new

    def remove(self, performance_id: str) -> Performance:
        performance = self.performance(performance_id)
        self.performances.remove(performance)
        return performance


# ---------- storage ----------


def load_festival(path: str = DATA_PATH) -> Festival:
    with open(path, encoding="utf-8") as file:
        return Festival.from_data(json.load(file))


def save_festival(festival: Festival, path: str = DATA_PATH) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(festival.to_data(), file, ensure_ascii=False, indent=2)
        file.write("\n")