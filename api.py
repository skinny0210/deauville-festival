from datetime import date, datetime

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from festival import NotFound, load_festival

app = FastAPI(title="Deauville Festival du Rire")


@app.exception_handler(NotFound)
async def handle_not_found(request, error: NotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


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


# After the routes: "/" would otherwise hide them.
app.mount("/", StaticFiles(directory="web/public", html=True), name="public")