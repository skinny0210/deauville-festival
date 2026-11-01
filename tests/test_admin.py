from datetime import datetime

import pytest

from deauville.errors import Conflict, Invalid, NotFound
from deauville.model import Festival, SoloShow


def at(text):
    return datetime.fromisoformat(text)


@pytest.fixture
def festival():
    return Festival.from_data(
        {
            "name": "T",
            "first_day": "2027-06-10",
            "last_day": "2027-06-13",
            "venues": [{"name": "Le Kiosque", "capacity": 120, "address": "x"}],
            "artists": [{"name": "Ana"}, {"name": "Maya"}, {"name": "Ben"}],
            "performances": [
                {"kind": "solo", "title": "A", "venue": "le-kiosque",
                 "start": "2027-06-13T11:00", "duration_minutes": 45,
                 "description": "", "artist": "ana", "min_age": 0},
                {"kind": "solo", "title": "M", "venue": "le-kiosque",
                 "start": "2027-06-13T15:00", "duration_minutes": 45,
                 "description": "", "artist": "maya", "min_age": 0},
            ],
        }
    )


def moved(festival, start):
    old = festival.performance("le-kiosque-2027-06-13-1100")
    return SoloShow(artist=old.artist, title=old.title, venue=old.venue,
                    start=at(start), duration_minutes=45)


def test_collections_cannot_be_changed_from_outside(festival):
    festival.performances.clear()
    festival.venues.clear()
    festival.artists.clear()
    assert len(festival.performances) == 2
    assert len(festival.venues) == 1
    assert len(festival.artists) == 3


def test_move_changes_the_id(festival):
    festival.replace("le-kiosque-2027-06-13-1100", moved(festival, "2027-06-13T12:00"))
    assert festival.performance("le-kiosque-2027-06-13-1200")
    with pytest.raises(NotFound):
        festival.performance("le-kiosque-2027-06-13-1100")


def test_refused_move_changes_nothing(festival):
    with pytest.raises(Conflict):
        festival.replace("le-kiosque-2027-06-13-1100", moved(festival, "2027-06-13T15:00"))
    assert festival.performance("le-kiosque-2027-06-13-1100")
    assert len(festival.performances) == 2


def test_duplicate_artist_is_refused(festival):
    festival.add_artist("Zoé Tanguy")
    with pytest.raises(Conflict):
        festival.add_artist("zoe tanguy")


def test_empty_artist_name_is_invalid(festival):
    with pytest.raises(Invalid):
        festival.add_artist("   ")


def test_error_family(festival):
    with pytest.raises(NotFound):
        festival.performance("nowhere-2027-06-13-1100")


def test_lineup_with_one_act_is_refused_from_a_body(festival):
    body = {"kind": "lineup", "title": "L", "venue": "le-kiosque",
            "start": "2027-06-12T20:00", "duration_minutes": 60,
            "host": "ana", "acts": ["ben"]}
    with pytest.raises(Invalid, match="at least 2 acts"):
        festival.add(festival.build(body))


def test_missing_field_is_invalid(festival):
    with pytest.raises(Invalid, match="missing"):
        festival.build({"kind": "solo", "title": "X", "venue": "le-kiosque",
                        "start": "2027-06-12T20:00", "duration_minutes": 30})


def test_workshop_registration_twice_is_refused(festival):
    festival.add(festival.build(
        {"kind": "workshop", "title": "W", "venue": "le-kiosque",
         "start": "2027-06-12T10:00", "duration_minutes": 60,
         "teacher": "ben", "max_participants": 5}))
    festival.register("le-kiosque-2027-06-12-1000", "Camille R.")
    with pytest.raises(Conflict):
        festival.register("le-kiosque-2027-06-12-1000", "camille r.")