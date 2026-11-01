from deauville.model import Festival
from deauville.storage import MemoryStorage

DATA = {
    "name": "T",
    "first_day": "2027-06-10",
    "last_day": "2027-06-13",
    "venues": [{"name": "Le Kiosque", "capacity": 120, "address": "x"}],
    "artists": [{"name": "Ana"}],
    "performances": [],
}


def test_memory_storage_round_trip():
    storage = MemoryStorage(DATA)
    festival = storage.load()
    festival.add_artist("Ben")
    storage.save(festival)
    assert len(storage.load().artists) == 2


def test_memory_storage_does_not_share_state():
    storage = MemoryStorage(DATA)
    storage.load().add_artist("Ben")  # not saved
    assert len(storage.load().artists) == 1
    assert isinstance(storage.load(), Festival)
