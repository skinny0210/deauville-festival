from datetime import date, datetime

import pytest

from deauville.errors import FestivalError

from deauville.model import Festival, NotFound


@pytest.fixture
def festival() -> Festival:
    """A small fresh festival for each test."""
    return Festival.from_data(
        {
            "name": "Test Festival",
            "first_day": "2027-06-10",
            "last_day": "2027-06-13",
            "venues": [
                {"name": "Le Kiosque", "capacity": 120, "address": "Beach"},
                {"name": "La Cabane", "capacity": 40, "address": "Beach"},
            ],
            "artists": [
                {"name": "Ana Roy"},
                {"name": "Ben Roy"},
                {"name": "Cleo Roy"},
                {"name": "Dan Roy"},
            ],
            "performances": [
                {
                    "kind": "solo",
                    "title": "Late Laughs",
                    "venue": "le-kiosque",
                    "start": "2027-06-11T23:30",
                    "duration_minutes": 60,
                    "description": "",
                    "artist": "ana-roy",
                    "min_age": 0,
                },
                {
                    "kind": "lineup",
                    "title": "Gala",
                    "venue": "la-cabane",
                    "start": "2027-06-10T20:30",
                    "duration_minutes": 120,
                    "description": "",
                    "host": "ben-roy",
                    "acts": ["cleo-roy", "dan-roy"],
                },
            ],
        }
    )


def at(text: str) -> datetime:
    return datetime.fromisoformat(text)


# ---------- venue and artist busy ----------


def test_venue_busy_is_refused(festival):
    with pytest.raises(FestivalError, match="Le Kiosque is busy with Late Laughs"):
        festival.schedule_solo("X", "ben-roy", "le-kiosque", at("2027-06-12T00:15"), 30)


def test_venue_gap_is_exactly_30_minutes(festival):
    # Late Laughs ends at 00:30: 01:00 is allowed, 00:59 is not.
    festival.schedule_solo("OK", "ben-roy", "le-kiosque", at("2027-06-12T01:00"), 30)
    with pytest.raises(FestivalError, match="busy"):
        festival.schedule_solo("No", "dan-roy", "le-kiosque", at("2027-06-12T00:59"), 5)


def test_artist_busy_in_another_venue_is_refused(festival):
    with pytest.raises(FestivalError, match="Ana Roy is on stage in Late Laughs"):
        festival.schedule_solo("X", "ana-roy", "la-cabane", at("2027-06-11T23:45"), 30)


def test_artist_busy_as_an_act_of_a_lineup_is_refused(festival):
    with pytest.raises(FestivalError, match="Cleo Roy is on stage in Gala"):
        festival.schedule_solo("X", "cleo-roy", "le-kiosque", at("2027-06-10T21:00"), 30)


def test_refused_performance_changes_nothing(festival):
    before = len(festival.performances)
    with pytest.raises(FestivalError):
        festival.schedule_solo("X", "ana-roy", "la-cabane", at("2027-06-11T23:45"), 30)
    assert len(festival.performances) == before


# ---------- time ----------


def test_show_at_one_am_belongs_to_the_previous_day(festival):
    new = festival.schedule_solo(
        "After", "ben-roy", "le-kiosque", at("2027-06-12T01:00"), 30
    )
    assert new.festival_day == date(2027, 6, 11)
    assert new in festival.programme(day=date(2027, 6, 11))
    assert new not in festival.programme(day=date(2027, 6, 12))


def test_day_after_the_festival_is_refused(festival):
    with pytest.raises(FestivalError, match="2027-06-14 is not a day of the festival"):
        festival.schedule_solo("X", "ben-roy", "la-cabane", at("2027-06-14T08:00"), 30)


def test_early_morning_before_the_first_day_is_refused(festival):
    # 03:00 on 10 June is still 9 June for the festival.
    with pytest.raises(FestivalError, match="not a day of the festival"):
        festival.schedule_solo("X", "ben-roy", "la-cabane", at("2027-06-10T03:00"), 30)


@pytest.mark.parametrize("minutes", [0, 361])
def test_duration_out_of_range_is_refused(festival, minutes):
    with pytest.raises(FestivalError, match="between 1 and 360"):
        festival.schedule_solo("X", "ben-roy", "la-cabane", at("2027-06-13T08:00"), minutes)


@pytest.mark.parametrize("minutes", [1, 360])
def test_duration_limits_are_accepted(festival, minutes):
    festival.schedule_solo("X", "ben-roy", "la-cabane", at("2027-06-13T08:00"), minutes)


# ---------- unknown things ----------


def test_unknown_venue_is_refused(festival):
    with pytest.raises(NotFound, match="No venue 'nowhere'"):
        festival.schedule_solo("X", "ana-roy", "nowhere", at("2027-06-13T08:00"), 30)


def test_unknown_artist_is_refused(festival):
    with pytest.raises(NotFound, match="No artist 'nobody'"):
        festival.schedule_solo("X", "nobody", "la-cabane", at("2027-06-13T08:00"), 30)


def test_unknown_performance_id_is_refused(festival):
    with pytest.raises(NotFound):
        festival.remove("nowhere-2027-06-13-0800")


# ---------- queries ----------


def test_performances_are_sorted_by_start(festival):
    titles = [p.title for p in festival.sorted_performances()]
    assert titles == ["Gala", "Late Laughs"]


def test_on_stage_and_up_next(festival):
    assert [p.title for p in festival.on_stage_at(at("2027-06-10T21:00"))] == ["Gala"]
    assert [p.title for p in festival.next_after(at("2027-06-10T21:00"))] == [
        "Late Laughs"
    ]


def test_end_is_not_on_stage(festival):
    assert festival.on_stage_at(at("2027-06-10T22:30")) == []


def test_cancel_frees_the_slot(festival):
    festival.remove("le-kiosque-2027-06-11-2330")
    festival.schedule_solo("Again", "ana-roy", "le-kiosque", at("2027-06-11T23:30"), 60)


def test_copy_of_performances_cannot_bypass_the_rules(festival):
    festival.performances.clear()
    assert len(festival.performances) == 2