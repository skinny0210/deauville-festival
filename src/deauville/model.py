from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from deauville.errors import Conflict, FestivalError, Invalid, NotFound
from deauville.parsing import clean_name, parse_moment, slugify

__all__ = [
    "Artist", "Conflict", "Festival", "FestivalError", "Invalid", "Lineup",
    "NotFound", "Performance", "SoloShow", "Venue", "Workshop",
]

DAY_ENDS_AT = timedelta(hours=6)
GAP = timedelta(minutes=30)
MIN_DURATION = 1
MAX_DURATION = 360
ACT_MINUTES = 10  # each act of a lineup
HOST_MINUTES = 3  # the host, between two acts
STAMP = "%Y-%m-%dT%H:%M"


# ---------- venues and artists ----------


@dataclass(eq=False)
class Venue:
    name: str
    capacity: int
    address: str

    def __post_init__(self) -> None:
        self.name = clean_name(self.name, "venue")
        if self.capacity < 1:
            raise Invalid(f"{self.name} needs at least 1 seat.")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Venue) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def __str__(self) -> str:
        return f"{self.slug}: {self.name}, {self.capacity} seats"

    def to_view(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "capacity": self.capacity,
            "address": self.address,
        }

    def to_data(self) -> dict:
        return {"name": self.name, "capacity": self.capacity, "address": self.address}


@dataclass(eq=False)
class Artist:
    name: str
    bio: str = ""
    photo_url: str = ""

    def __post_init__(self) -> None:
        self.name = clean_name(self.name, "artist")

    @property
    def slug(self) -> str:
        return slugify(self.name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Artist) and self.slug == other.slug

    def __hash__(self) -> int:
        return hash(self.slug)

    def __str__(self) -> str:
        return self.name

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


# ---------- performances: one base class, three kinds ----------


class Performance(ABC):
    """What every performance shares. Cannot be created directly."""

    kind: str = ""  # each subclass sets its own

    def __init__(
        self,
        title: str,
        venue: Venue,
        start: datetime,
        duration_minutes: int,
        description: str = "",
    ) -> None:
        self.title = clean_name(title, "performance")
        self.venue = venue
        self.start = start
        self.duration_minutes = duration_minutes
        self.description = description

    @property
    @abstractmethod
    def people(self) -> list[tuple[Artist, str]]:
        """The (artist, role) pairs on stage."""

    @property
    @abstractmethod
    def summary(self) -> str: ...

    @abstractmethod
    def validate(self) -> None:
        """Raise Invalid if the rules of this kind are broken."""

    @abstractmethod
    def extra_view(self) -> dict:
        """The fields of the API that only this kind has."""

    @abstractmethod
    def extra_data(self) -> dict:
        """The fields of the file that only this kind has."""

    @classmethod
    @abstractmethod
    def from_data(cls, item: dict, festival: "Festival") -> "Performance": ...

    @staticmethod
    def common_fields(item: dict, festival: "Festival") -> dict:
        return {
            "title": item["title"],
            "venue": festival.venue(item["venue"]),
            "start": parse_moment(item["start"]),
            "duration_minutes": item["duration_minutes"],
            "description": item.get("description", ""),
        }

    def __lt__(self, other: "Performance") -> bool:
        return (self.start, self.venue.name) < (other.start, other.venue.name)

    def __str__(self) -> str:
        return f"{self.time_range()} | {self.venue.name} | {self.title} ({self.kind})"

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

    def involves(self, artist: Artist) -> bool:
        return any(person == artist for person, _ in self.people)

    def role_of(self, artist: Artist) -> str:
        for person, role in self.people:
            if person == artist:
                return role
        raise Invalid(f"{artist.name} is not on stage in {self.title}.")

    def clashes_with(self, other: "Performance", gap: timedelta = GAP) -> bool:
        return self.start < other.end + gap and other.start < self.end + gap

    def time_range(self) -> str:
        return f"{self.start:%H:%M}-{self.end:%H:%M}"

    def full_range(self) -> str:
        return f"{self.start:%Y-%m-%d %H:%M}-{self.end:%H:%M}"

    def programme_line(self) -> str:
        return str(self)

    def artist_line(self, role: str) -> str:
        return (
            f"{self.festival_day:%a %d} {self.time_range()} | "
            f"{self.venue.name} | {self.title} ({role})"
        )

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
        view.update(self.extra_view())
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
        data.update(self.extra_data())
        return data


class SoloShow(Performance):
    kind = "solo"

    def __init__(self, artist: Artist, min_age: int = 0, **common: object) -> None:
        super().__init__(**common)
        self.artist = artist
        self.min_age = min_age
        self.validate()

    def validate(self) -> None:
        if not 0 <= self.min_age <= 18:
            raise Invalid("The minimum age of a solo show must be between 0 and 18.")

    @property
    def people(self) -> list[tuple[Artist, str]]:
        return [(self.artist, "solo")]

    @property
    def summary(self) -> str:
        return self.artist.name

    def extra_view(self) -> dict:
        return {"artist": self.artist.slug, "min_age": self.min_age}

    def extra_data(self) -> dict:
        return {"artist": self.artist.slug, "min_age": self.min_age}

    @classmethod
    def from_data(cls, item: dict, festival: "Festival") -> "SoloShow":
        return cls(
            artist=festival.artist(item["artist"]),
            min_age=item.get("min_age", 0),
            **cls.common_fields(item, festival),
        )


class Lineup(Performance):
    kind = "lineup"

    def __init__(self, host: Artist, acts: list[Artist], **common: object) -> None:
        super().__init__(**common)
        self.host = host
        self._acts = list(acts)
        self.validate()

    @property
    def acts(self) -> list[Artist]:
        """A copy: the acts cannot be changed from outside."""
        return list(self._acts)

    @property
    def minimum_minutes(self) -> int:
        count = len(self._acts)
        return count * ACT_MINUTES + max(count - 1, 0) * HOST_MINUTES

    def validate(self) -> None:
        if len(self._acts) < 2:
            raise Invalid(f"{self.title} needs at least 2 acts.")
        for index, act in enumerate(self._acts):
            if act in self._acts[:index]:
                raise Invalid(f"{act.name} is twice in {self.title}.")
        if self.host in self._acts:
            raise Invalid(f"{self.host.name} is the host of {self.title}, not an act.")
        if self.duration_minutes < self.minimum_minutes:
            raise Invalid(
                f"{self.title} has {len(self._acts)} acts and needs at least "
                f"{self.minimum_minutes} minutes."
            )

    @property
    def people(self) -> list[tuple[Artist, str]]:
        return [(self.host, "host")] + [(act, "act") for act in self._acts]

    @property
    def summary(self) -> str:
        acts = ", ".join(act.name for act in self._acts)
        return f"hosted by {self.host.name}, with {acts}"

    def extra_view(self) -> dict:
        return {"host": self.host.slug, "acts": [act.slug for act in self._acts]}

    def extra_data(self) -> dict:
        return self.extra_view()

    @classmethod
    def from_data(cls, item: dict, festival: "Festival") -> "Lineup":
        return cls(
            host=festival.artist(item["host"]),
            acts=[festival.artist(slug) for slug in item["acts"]],
            **cls.common_fields(item, festival),
        )


class Workshop(Performance):
    kind = "workshop"

    def __init__(
        self,
        teacher: Artist,
        max_participants: int,
        participants: list[str] | None = None,
        **common: object,
    ) -> None:
        super().__init__(**common)
        self.teacher = teacher
        self.max_participants = max_participants
        self._participants = [clean_name(p, "participant") for p in participants or []]
        self.validate()

    @property
    def participants(self) -> list[str]:
        """A copy: use register() to add someone."""
        return list(self._participants)

    def validate(self) -> None:
        if self.max_participants < 1:
            raise Invalid(f"{self.title} needs at least 1 place.")
        if len(self._participants) > self.places:
            raise Invalid(f"{self.title} has more participants than places.")

    @property
    def places(self) -> int:
        return min(self.max_participants, self.venue.capacity)

    @property
    def places_left(self) -> int:
        return self.places - len(self._participants)

    @property
    def capacity(self) -> int:
        return self.places

    def register(self, name: str) -> None:
        name = clean_name(name, "participant")
        if name.casefold() in (p.casefold() for p in self._participants):
            raise Conflict(f"{name} is already registered for {self.title}.")
        if self.places_left == 0:
            raise Conflict(f"{self.title} is full.")
        self._participants.append(name)

    @property
    def people(self) -> list[tuple[Artist, str]]:
        return [(self.teacher, "teacher")]

    @property
    def summary(self) -> str:
        return (
            f"with {self.teacher.name}, "
            f"{len(self._participants)}/{self.places} places taken"
        )

    def extra_view(self) -> dict:
        return {
            "teacher": self.teacher.slug,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
            "places_left": self.places_left,
        }

    def extra_data(self) -> dict:
        return {
            "teacher": self.teacher.slug,
            "max_participants": self.max_participants,
            "participants": list(self._participants),
        }

    @classmethod
    def from_data(cls, item: dict, festival: "Festival") -> "Workshop":
        return cls(
            teacher=festival.artist(item["teacher"]),
            max_participants=item["max_participants"],
            participants=item.get("participants", []),
            **cls.common_fields(item, festival),
        )


# The "kind" field chooses the class, here and nowhere else.
PERFORMANCE_KINDS: dict[str, type[Performance]] = {
    cls.kind: cls for cls in (SoloShow, Lineup, Workshop)
}


# ---------- the festival ----------


class Festival:
    """Holds venues, artists and the schedule. It does not know where it is
    stored (see storage.py). Collections are private: the only way to change
    them is through the methods below, which apply the rules."""

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
        self._venues = list(venues)
        self._artists = list(artists)
        self._performances: list[Performance] = []

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
            festival.add(festival.build(item))
        return festival

    def build(self, item: dict) -> Performance:
        """Turn a dict (file or request body) into a performance, not yet added."""
        try:
            performance_class = PERFORMANCE_KINDS[item.get("kind")]
        except KeyError:
            raise Invalid(f"'{item.get('kind')}' is not a kind of performance.") from None
        try:
            return performance_class.from_data(item, self)
        except KeyError as error:
            raise Invalid(f"The field {error.args[0]} is missing.") from None

    def to_data(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "venues": [v.to_data() for v in self._venues],
            "artists": [a.to_data() for a in self._artists],
            "performances": [p.to_data() for p in self._performances],
        }

    def to_view(self) -> dict:
        return {
            "name": self.name,
            "first_day": self.first_day.isoformat(),
            "last_day": self.last_day.isoformat(),
            "days": [day.isoformat() for day in self.days],
        }

    # reading (always copies)
    @property
    def days(self) -> list[date]:
        count = (self.last_day - self.first_day).days + 1
        return [self.first_day + timedelta(days=i) for i in range(count)]

    @property
    def venues(self) -> list[Venue]:
        return list(self._venues)

    @property
    def artists(self) -> list[Artist]:
        return list(self._artists)

    @property
    def performances(self) -> list[Performance]:
        return list(self._performances)

    def venue(self, slug: str) -> Venue:
        for venue in self._venues:
            if venue.slug == slug:
                return venue
        raise NotFound(f"No venue '{slug}'.")

    def artist(self, slug: str) -> Artist:
        for artist in self._artists:
            if artist.slug == slug:
                return artist
        raise NotFound(f"No artist '{slug}'.")

    def performance(self, performance_id: str) -> Performance:
        for performance in self._performances:
            if performance.id == performance_id:
                return performance
        raise NotFound(f"No performance with id '{performance_id}'.")

    def artists_sorted(self) -> list[Artist]:
        return sorted(self._artists, key=lambda a: a.slug)

    def sorted_performances(self) -> list[Performance]:
        return sorted(self._performances)

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

    # rules common to every kind (the rules of each kind live in its class)
    def check(self, new: Performance, ignoring: Performance | None = None) -> None:
        """Raise a FestivalError if `new` breaks a rule. `ignoring` is the old
        version of a performance that is being moved."""
        if not MIN_DURATION <= new.duration_minutes <= MAX_DURATION:
            raise Invalid(
                f"A duration must be between {MIN_DURATION} and {MAX_DURATION} minutes."
            )
        new.validate()
        if not self.first_day <= new.festival_day <= self.last_day:
            raise Invalid(
                f"{new.festival_day.isoformat()} is not a day of the festival."
            )

        for other in self._performances:
            if other is ignoring:
                continue
            if other.venue == new.venue and new.clashes_with(other):
                raise Conflict(
                    f"{new.venue.name} is busy with {other.title} ({other.full_range()}). "
                    "Leave 30 minutes between two shows."
                )
        for artist, _role in new.people:
            for other in self._performances:
                if other is ignoring:
                    continue
                if other.involves(artist) and new.clashes_with(other):
                    raise Conflict(
                        f"{artist.name} is on stage in {other.title}. "
                        "Leave 30 minutes between two shows."
                    )

    # changes (the only doors)
    def add(self, performance: Performance) -> None:
        """Check every rule, then add. A refused performance changes nothing."""
        self.check(performance)
        self._performances.append(performance)

    def replace(self, performance_id: str, new: Performance) -> Performance:
        """Swap a performance for a new version. If a rule refuses, nothing changes."""
        old = self.performance(performance_id)
        self.check(new, ignoring=old)
        self._performances[self._performances.index(old)] = new
        return new

    def remove(self, performance_id: str) -> Performance:
        performance = self.performance(performance_id)
        self._performances.remove(performance)
        return performance

    def register(self, performance_id: str, name: str) -> Workshop:
        performance = self.performance(performance_id)
        if not isinstance(performance, Workshop):
            raise Invalid(f"{performance.title} is not a workshop.")
        performance.register(name)
        return performance

    def add_artist(self, name: str, bio: str = "", photo_url: str = "") -> Artist:
        artist = Artist(name, bio, photo_url)
        if any(a == artist for a in self._artists):
            raise Conflict(f"The artist '{artist.slug}' already exists.")
        self._artists.append(artist)
        return artist

    def schedule_solo(
        self,
        title: str,
        artist_slug: str,
        venue_slug: str,
        start: datetime,
        minutes: int,
        min_age: int = 0,
    ) -> Performance:
        new = SoloShow(
            artist=self.artist(artist_slug),
            min_age=min_age,
            title=title,
            venue=self.venue(venue_slug),
            start=start,
            duration_minutes=minutes,
        )
        self.add(new)
        return new