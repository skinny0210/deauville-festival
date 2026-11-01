import shutil

import pytest
from fastapi.testclient import TestClient

from deauville.api import create_app
from deauville.storage import JsonStorage

AFTER_HOURS = "le-kiosque-2027-06-12-0100"
IMPROV = "la-cabane-2027-06-11-1030"
STANDUP = "la-cabane-2027-06-12-1030"


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "festival.json"
    shutil.copy("data/festival.json", path)
    return path


@pytest.fixture
def client(data_file):
    return TestClient(create_app(JsonStorage(str(data_file))))


def solo(start="2027-06-13T11:00", artist="nora-lebrun", venue="le-kiosque"):
    return {
        "kind": "solo",
        "title": "Test Show",
        "venue": venue,
        "start": start,
        "duration_minutes": 45,
        "artist": artist,
        "min_age": 0,
    }


# ---------- reading ----------


def test_festival(client):
    body = client.get("/api/festival").json()
    assert body["first_day"] == "2027-06-10"
    assert body["days"] == ["2027-06-10", "2027-06-11", "2027-06-12", "2027-06-13"]


def test_venues_keep_file_order(client):
    slugs = [v["slug"] for v in client.get("/api/venues").json()]
    assert slugs[0] == "grand-casino" and len(slugs) == 4


def test_artists_sorted_by_slug(client):
    artists = client.get("/api/artists").json()
    assert artists[0]["slug"] == "elodie-marchal" and len(artists) == 12


def test_artist_with_performances(client):
    body = client.get("/api/artists/max-pellerin").json()
    assert len(body["performances"]) == 4


def test_unknown_artist_is_404(client):
    response = client.get("/api/artists/nobody")
    assert response.status_code == 404
    assert response.json() == {"detail": "No artist 'nobody'."}


def test_programme_filters(client):
    assert len(client.get("/api/programme?venue=le-kiosque").json()) == 7
    friday = client.get("/api/programme?day=2027-06-11").json()
    assert friday[-1]["id"] == AFTER_HOURS


def test_programme_unknown_venue_is_404(client):
    response = client.get("/api/programme?venue=nowhere")
    assert response.status_code == 404
    assert response.json() == {"detail": "No venue 'nowhere'."}


def test_programme_bad_day_is_422(client):
    assert client.get("/api/programme?day=June 11").status_code == 422


def test_performance(client):
    body = client.get(f"/api/performances/{AFTER_HOURS}").json()
    assert body["summary"] == "hosted by Tom Vasseur, with Hugo Lemaire, Maya Choukri"
    assert body["festival_day"] == "2027-06-11"


def test_workshop_places_left(client):
    assert client.get(f"/api/performances/{IMPROV}").json()["places_left"] == 9


def test_unknown_performance_is_404(client):
    assert client.get("/api/performances/nowhere-2027-06-13-1100").status_code == 404


def test_now(client):
    body = client.get("/api/now?at=2027-06-11T21:00").json()
    assert [p["title"] for p in body["now_playing"]] == ["Tall Tales"]
    assert len(body["up_next"]) == 3


# ---------- writing ----------


def test_create_solo(client):
    response = client.post("/api/performances", json=solo())
    assert response.status_code == 201
    assert response.json()["id"] == "le-kiosque-2027-06-13-1100"
    assert client.get("/api/performances/le-kiosque-2027-06-13-1100").status_code == 200


def test_create_is_saved_to_the_file(client, data_file):
    client.post("/api/performances", json=solo())
    assert "Test Show" in data_file.read_text(encoding="utf-8")


def test_venue_busy_is_409(client):
    client.post("/api/performances", json=solo())
    response = client.post("/api/performances", json=solo("2027-06-13T11:30"))
    assert response.status_code == 409
    assert "Le Kiosque is busy" in response.json()["detail"]


def test_artist_busy_is_409(client):
    client.post("/api/performances", json=solo())
    other = solo("2027-06-13T12:00", venue="grand-casino")
    response = client.post("/api/performances", json=other)
    assert response.status_code == 409
    assert "Nora Lebrun is on stage" in response.json()["detail"]


def test_lineup_with_one_act_is_422(client):
    body = {
        "kind": "lineup",
        "title": "L",
        "venue": "la-cabane",
        "start": "2027-06-13T09:00",
        "duration_minutes": 60,
        "host": "tom-vasseur",
        "acts": ["hugo-lemaire"],
    }
    response = client.post("/api/performances", json=body)
    assert response.status_code == 422
    assert "at least 2 acts" in response.json()["detail"]


def test_unknown_artist_in_body_is_404(client):
    response = client.post("/api/performances", json=solo(artist="nobody"))
    assert response.status_code == 404


def test_day_outside_festival_is_409(client):
    response = client.post("/api/performances", json=solo("2027-06-14T11:00"))
    assert response.status_code == 409


def test_missing_field_is_422(client):
    assert client.post("/api/performances", json={"kind": "solo"}).status_code == 422


def test_put_changes_the_id(client):
    client.post("/api/performances", json=solo())
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1100", json=solo("2027-06-13T12:00")
    )
    assert response.status_code == 200
    assert response.json()["id"] == "le-kiosque-2027-06-13-1200"
    old = client.get("/api/performances/le-kiosque-2027-06-13-1100")
    assert old.status_code == 404


def test_refused_put_changes_nothing(client):
    client.post("/api/performances", json=solo("2027-06-13T12:00"))
    response = client.put(
        "/api/performances/le-kiosque-2027-06-13-1200", json=solo("2027-06-13T15:00")
    )
    assert response.status_code == 409
    assert client.get("/api/performances/le-kiosque-2027-06-13-1200").status_code == 200


def test_put_unknown_is_404(client):
    response = client.put("/api/performances/nowhere-2027-06-13-1100", json=solo())
    assert response.status_code == 404


def test_delete_twice(client):
    assert client.delete(f"/api/performances/{AFTER_HOURS}").status_code == 204
    assert client.delete(f"/api/performances/{AFTER_HOURS}").status_code == 404


# ---------- workshops and artists ----------


def test_register_twice_is_409(client):
    url = f"/api/performances/{IMPROV}/participants"
    assert client.post(url, json={"name": "Zoé T."}).status_code == 201
    assert client.post(url, json={"name": "zoé t."}).status_code == 409


def test_full_workshop_is_409(client):
    url = f"/api/performances/{STANDUP}/participants"
    for number in range(6):  # 4 already registered, 10 places
        assert client.post(url, json={"name": f"Person {number}"}).status_code == 201
    response = client.post(url, json={"name": "One more"})
    assert response.status_code == 409
    assert "full" in response.json()["detail"]


def test_register_in_a_solo_is_422(client):
    url = f"/api/performances/{AFTER_HOURS}/participants"
    assert client.post(url, json={"name": "X"}).status_code == 422


def test_add_artist_twice_is_409(client):
    assert client.post("/api/artists", json={"name": "Zoé Tanguy"}).status_code == 201
    assert client.post("/api/artists", json={"name": "zoe tanguy"}).status_code == 409


def test_empty_artist_name_is_422(client):
    assert client.post("/api/artists", json={"name": "  "}).status_code == 422


# ---------- the file ----------


def test_unwritable_file_is_500(data_file):
    class BrokenStorage(JsonStorage):
        def save(self, festival):
            raise OSError("disk full")

    client = TestClient(create_app(BrokenStorage(str(data_file))))
    response = client.post("/api/artists", json={"name": "Zoé Tanguy"})
    assert response.status_code == 500
    assert "detail" in response.json()


def test_damaged_file_is_500(data_file):
    data_file.write_text("{ not json", encoding="utf-8")
    client = TestClient(create_app(JsonStorage(str(data_file))))
    assert client.get("/api/festival").status_code == 500
