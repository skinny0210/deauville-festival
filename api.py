from datetime import date, datetime

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from festival import (
    Conflict,
    FestivalError,
    Invalid,
    NotFound,
    load_festival,
    save_festival,
)

app = FastAPI(title="Deauville Festival du Rire")

STATUS = {NotFound: 404, Conflict: 409, Invalid: 422}


@app.exception_handler(FestivalError)
async def handle_festival_error(request, error: FestivalError) -> JSONResponse:
    status = next((s for t, s in STATUS.items() if isinstance(error, t)), 500)
    return JSONResponse(status_code=status, content={"detail": str(error)})


# ---------- request bodies ----------


class PerformanceBody(BaseModel):
    kind: str
    title: str
    venue: str
    start: str
    duration_minutes: int
    description: str = ""
    artist: str | None = None  # solo
    min_age: int = 0  # solo
    host: str | None = None  # lineup
    acts: list[str] = []  # lineup
    teacher: str | None = None  # workshop
    max_participants: int | None = None  # workshop
    participants: list[str] | None = None  # workshop


class ParticipantBody(BaseModel):
    name: str


class ArtistBody(BaseModel):
    name: str
    bio: str = ""
    photo_url: str = ""


# ---------- read ----------


@app.get("/api/festival")
def get_festival() -> dict:
    return load_festival().to_view()


@app.get("/api/venues")
def list_venues() -> list[dict]:
    return [venue.to_view() for venue in load_festival().venues]


@app.get("/api/artists")
def list_artists() -> list[dict]:
    return [artist.to_view() for artist in load_festival().artists_sorted()]


@app.get("/api/artists/{slug}")
def get_artist(slug: str) -> dict:
    festival = load_festival()
    artist = festival.artist(slug)
    return {
        **artist.to_view(),
        "performances": [
            {**performance.to_view(), "role": role}
            for performance, role in festival.appearances_of(artist)
        ],
    }


@app.get("/api/programme")
def get_programme(day: date | None = None, venue: str | None = None) -> list[dict]:
    festival = load_festival()
    return [p.to_view() for p in festival.programme(day=day, venue_slug=venue)]


@app.get("/api/performances/{performance_id}")
def get_performance(performance_id: str) -> dict:
    return load_festival().performance(performance_id).to_view()


@app.get("/api/now")
def get_now(at: datetime | None = None) -> dict:
    festival = load_festival()
    moment = at if at is not None else datetime.now()
    return {
        "at": moment.strftime("%Y-%m-%dT%H:%M"),
        "now_playing": [p.to_view() for p in festival.on_stage_at(moment)],
        "up_next": [p.to_view() for p in festival.next_after(moment, 3)],
    }


# ---------- write (admin) ----------


@app.post("/api/performances", status_code=201)
def create_performance(body: PerformanceBody) -> dict:
    festival = load_festival()
    new = festival.build(body.model_dump(exclude_none=True))
    festival.add(new)
    save_festival(festival)
    return new.to_view()


@app.put("/api/performances/{performance_id}")
def update_performance(performance_id: str, body: PerformanceBody) -> dict:
    festival = load_festival()
    old = festival.performance(performance_id)
    item = body.model_dump(exclude_none=True)
    # a workshop edited without its participants keeps them
    previous = getattr(old, "participants", None)
    if previous is not None and body.kind == old.kind and body.participants is None:
        item["participants"] = previous
    new = festival.replace(performance_id, festival.build(item))
    save_festival(festival)
    return new.to_view()


@app.delete("/api/performances/{performance_id}", status_code=204)
def delete_performance(performance_id: str) -> Response:
    festival = load_festival()
    festival.remove(performance_id)
    save_festival(festival)
    return Response(status_code=204)


@app.post("/api/performances/{performance_id}/participants", status_code=201)
def register_participant(performance_id: str, body: ParticipantBody) -> dict:
    festival = load_festival()
    workshop = festival.register(performance_id, body.name)
    save_festival(festival)
    return workshop.to_view()


@app.post("/api/artists", status_code=201)
def create_artist(body: ArtistBody) -> dict:
    festival = load_festival()
    artist = festival.add_artist(body.name, body.bio, body.photo_url)
    save_festival(festival)
    return artist.to_view()


# After the routes: "/admin/" before "/", or "/" would hide it.
app.mount("/admin", StaticFiles(directory="web/admin", html=True), name="admin")
app.mount("/", StaticFiles(directory="web/public", html=True), name="public")