# Deauville Festival du Rire

Platform for the programme of the festival (10-13 June 2027): venues, artists and
three kinds of performances (solo, lineup, workshop), with the scheduling rules
of the brief. A command line, an HTTP API and the website/admin on top of it.

## Install and run

    uv sync
    uv run deauville                       # summary
    uv run deauville programme 2027-06-11  # programme of a festival day
    uv run deauville artist max-pellerin
    uv run deauville now 2027-06-12T01:30
    uv run deauville venues
    uv run deauville add / cancel ID
    uv run deauville serve                 # website, admin and API on :8000
    uv run deauville --data other.json ... # use another data file
    uv run pytest                          # tests
    uv build                               # wheel in dist/

Run `serve` from the project root: it reads `web/` from the current folder.

## Structure

- `src/deauville/errors.py`: `FestivalError` and its family `NotFound` (404),
  `Conflict` (409), `Invalid` (422).
- `parsing.py`: slugs, names, parsing of days, moments and minutes.
- `model.py`: `Venue`, `Artist`, abstract `Performance` and its subclasses
  `SoloShow`, `Lineup`, `Workshop`, and `Festival`.
- `storage.py`: `Storage` interface, `JsonStorage`, `MemoryStorage`.
- `api.py`: `create_app(storage)`, the routes of API.md.
- `cli.py`: the commands, `--data`, `serve`.

## Why this structure

- **Where the rules live**: in `Festival.check` (venue, artists, days, duration) and
  in the `validate` of each kind (age, acts, places). The collections of
  `Festival` are private and read through copies, so the only ways to change the
  schedule are `add`, `replace`, `remove`, `register` and `add_artist`, which all
  apply the rules. The command line and the API cannot bypass them.
- **How errors say which rule**: each error has a type. The command line
  catches the family; the API maps each type to a status in one handler.
- **Kinds**: the common part (start, end, festival day, id, views) is in
  `Performance`; each kind writes its people, summary, rules and fields. The
  file's `kind` picks the class once, in `PERFORMANCE_KINDS`.
- **With a database**: only `storage.py` changes (a new `Storage`
  implementation); `model.py`, `api.py` and `cli.py` stay the same.

## Done and not done

- Done: all commands, all routes of API.md, rules, tests through `TestClient`
  on a copy of the data, package and wheel.
- Not done: no SQLite storage; every request reloads and rewrites the whole
  file; `web/` and `data/` are not in the wheel, so `serve` needs the project
  folder.
- Known bugs: none known.