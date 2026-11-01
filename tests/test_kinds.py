from datetime import datetime

import pytest

from deauville.errors import FestivalError
from deauville.model import (
    Festival,
    Lineup,
    Performance,
    SoloShow,
    Workshop,
)


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


@pytest.fixture
def festival() -> Festival:
    return Festival.from_data(
        {
            "name": "Test",
            "first_day": "2027-06-10",
            "last_day": "2027-06-13",
            "venues": [
                {"name": "Grand Casino", "capacity": 650, "address": "x"},
                {"name": "La Cabane", "capacity": 40, "address": "x"},
            ],
            "artists": [{"name": n} for n in ("Ana", "Ben", "Cleo", "Dan", "Eva")],
            "performances": [],
        }
    )


def common(festival, venue="la-cabane", start="2027-06-11T18:00", minutes=60):
    return {
        "title": "T",
        "venue": festival.venue(venue),
        "start": at(start),
        "duration_minutes": minutes,
    }


def lineup(festival, acts, minutes):
    return Lineup(
        host=festival.artist("ana"),
        acts=[festival.artist(slug) for slug in acts],
        **common(festival, minutes=minutes),
    )


def test_a_bare_performance_cannot_be_created(festival):
    with pytest.raises(TypeError):
        Performance(**common(festival))


@pytest.mark.parametrize("age", [-1, 19])
def test_solo_age_out_of_range_is_refused(festival, age):
    with pytest.raises(FestivalError, match="between 0 and 18"):
        SoloShow(artist=festival.artist("ana"), min_age=age, **common(festival))


@pytest.mark.parametrize("age", [0, 18])
def test_solo_age_limits_are_accepted(festival, age):
    SoloShow(artist=festival.artist("ana"), min_age=age, **common(festival))


def test_lineup_of_3_acts_needs_36_minutes(festival):
    with pytest.raises(FestivalError, match="at least 36 minutes"):
        lineup(festival, ["ben", "cleo", "dan"], 35)
    festival.add(lineup(festival, ["ben", "cleo", "dan"], 36))


def test_lineup_needs_two_acts(festival):
    with pytest.raises(FestivalError, match="at least 2 acts"):
        lineup(festival, ["ben"], 60)


def test_lineup_act_only_once(festival):
    with pytest.raises(FestivalError, match="twice"):
        lineup(festival, ["ben", "ben"], 60)


def test_lineup_host_is_not_an_act(festival):
    with pytest.raises(FestivalError, match="not an act"):
        lineup(festival, ["ana", "ben"], 60)


def test_workshop_needs_one_place(festival):
    with pytest.raises(FestivalError, match="at least 1 place"):
        Workshop(teacher=festival.artist("ana"), max_participants=0, **common(festival))


def test_workshop_places_are_limited_by_the_venue(festival):
    big = Workshop(
        teacher=festival.artist("ana"),
        max_participants=999,
        **common(festival, venue="grand-casino"),
    )
    assert big.places == 650


def test_workshop_registration_ignores_case_and_stops_when_full(festival):
    workshop = Workshop(
        teacher=festival.artist("ana"), max_participants=2, **common(festival)
    )
    workshop.register("Camille R.")
    with pytest.raises(FestivalError, match="already registered"):
        workshop.register("camille r.")
    workshop.register("Yanis B.")
    with pytest.raises(FestivalError, match="full"):
        workshop.register("Lou M.")


def test_summaries(festival):
    solo = SoloShow(artist=festival.artist("eva"), **common(festival))
    workshop = Workshop(
        teacher=festival.artist("ana"),
        max_participants=12,
        participants=["a", "b", "c"],
        **common(festival),
    )
    assert solo.summary == "Eva"
    assert workshop.summary == "with Ana, 3/12 places taken"
    assert (
        lineup(festival, ["ben", "cleo"], 60).summary == "hosted by Ana, with Ben, Cleo"
    )


def test_unknown_kind_in_the_file_is_refused():
    data = {
        "name": "T",
        "first_day": "2027-06-10",
        "last_day": "2027-06-13",
        "venues": [{"name": "A", "capacity": 10, "address": "x"}],
        "artists": [{"name": "Ana"}],
        "performances": [
            {
                "kind": "circus",
                "title": "X",
                "venue": "a",
                "start": "2027-06-11T18:00",
                "duration_minutes": 30,
            }
        ],
    }
    with pytest.raises(FestivalError, match="not a kind of performance"):
        Festival.from_data(data)
