from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from festival import artist_objects, festival_object, load_festival, venue_objects

app = FastAPI(title="Deauville Festival du Rire")


@app.get("/api/festival")
def get_festival() -> dict:
    return festival_object(load_festival())


@app.get("/api/venues")
def list_venues() -> list[dict]:
    return venue_objects(load_festival())


@app.get("/api/artists")
def list_artists() -> list[dict]:
    return artist_objects(load_festival())


# After the routes: "/" would otherwise hide them.
app.mount("/", StaticFiles(directory="web/public", html=True), name="public")