# Flask → FastAPI Migration Plan

## Progress

**Done**
- Env consolidated on `replay-rythms/` (Python 3.13.0); stray `.venv/` deleted
- `fastapi 0.141.1`, `uvicorn 0.52.3`, `pydantic 2.13.4` installed into it
- `Dockerfile:2` bumped `python:3.11-slim` → `python:3.13-slim` (comment on line 1 fixed too)

**In progress**
- Fixing the `matched_criteria` set-ordering bug in `song_matcher.py`

**Next**
- Write `main.py`

**Not started**
- `requirements.txt` still missing `fastapi`/`uvicorn`/`pydantic` — drifted from the venv
- Nothing committed yet; last commit is `a7b1604`

## Goal

Convert the existing Flask API to FastAPI without changing observable behavior.

## Scope: it's one file

Measured, not assumed:

| | Lines | Framework coupling |
|---|---|---|
| `app.py` | 471 | **only file importing flask** |
| everything else | 2,214 | none — pure Python |
| tests | 0 | — |

Inside `app.py`:
- lines 1–275 — plain functions (`get_song_recommendation_profile`, `get_agentic_recommendation_profile`, `get_song_recommendations`). Only two Flask touchpoints in the whole range, both `app.logger.error` inside `except` blocks (lines 201, 271).
- lines 276–471 — routes and error handlers. **This is where the actual rewrite happens.**

The originally considered "new folder, migrate module by module" approach was **dropped**: there is only one module to migrate.

## Decision: `main.py` beside `app.py`

New FastAPI app goes in `main.py` at repo root. `app.py` stays untouched until cutover.

Not a new folder, and not an in-place edit of `app.py`.

Reason: both servers must be runnable *at the same time* to compare responses.

```
gunicorn app:app --bind 0.0.0.0:8000     # Flask,   old
uvicorn main:app --port 8001             # FastAPI, new
```

Editing `app.py` in place leaves only one of the two runnable at any moment, which makes every comparison a memory exercise.

## Decision: handlers stay `def`, not `async def`

`game_analyst.py:189` calls the **synchronous** OpenAI client on the `/recommend` path.

FastAPI runs `def` handlers in a threadpool but `async def` handlers on the event loop. An `async def` handler calling that blocking client stalls the event loop for the whole LLM call — worse than Flask's current behavior.

So: keep handlers as `def`. Only convert a handler to `async def` after the IO underneath it is genuinely awaitable (`AsyncOpenAI`). Async is not a win on its own.

Other blocking IO (`requests` in `enrich_songs.py`, `spotify_url_fixer.py`) is in offline scripts, not the request path — not a concern for this migration.

## Verification strategy: two-server response diff

**Golden files are dropped.** Delete `golden/` and `generate_golden_tests.py`.

The reasoning evolved twice, both times narrowing:

1. First draft said golden-file every pure module. Over-broad — `extract_data.py` is pure dict passthrough and `metrics.py` is IEEE 754 float math. Neither is threatened by a 3.11 → 3.13 bump or a web-framework swap.
2. Second draft narrowed to `app.py:143–275`, on the theory that rewritten code is where drift happens. But that range has only **two** Flask touchpoints (both `app.logger.error`). It isn't being rewritten — it's being copy-pasted with two logger lines swapped. Snapshotting a verbatim move is also ceremony.

The instrument that actually matches the risk is the **two-server response diff**:

```
gunicorn app:app --bind 0.0.0.0:8000     # old
uvicorn main:app --port 8001             # new
# same request to both, diff the JSON
```

It is a strict superset of what goldens would have caught: everything the internal functions do, **plus** the route layer (`app.py:276–471`) that is genuinely being rewritten — request parsing, Pydantic models, error handlers, response serialization. Running both instruments would be pure cost.

### What to compare, and what not to

`USE_AGENTIC` (`app.py:231`) decides how deep the diff can go:

| `USE_AGENTIC` | Path | Comparable |
|---|---|---|
| `false` | pure: extract → metrics → threshold → rule_engine → song_matcher | **full response body, exact diff** |
| `true` | routes through `analyze_game()` → LLM | **contract only** — status code, JSON shape, required keys, error responses. Not which songs came back |

Run the bulk of verification with `USE_AGENTIC=false`. That path is deterministic end-to-end and exercises nearly every pure module in the repo.

Also worth pinning: a few fixed replay fixtures that land in *different* threshold buckets — a blowout win, a close loss, an overtime game. One replay only exercises one branch through `threshold.py`.

## Blocker: nondeterministic `matched_criteria`

Must be fixed **before** the two-server diff. This is load-bearing, not optional housekeeping.

```python
# song_matcher.py:87-100
desired_moods = set(desired_profile.get("moods") or [])
song_moods   = set(song.get("moods") or [])
common = desired_moods & song_moods
matched.append(f"Moods {', '.join(common)}")     # ← joined in set-iteration order
```

Python randomizes string hashes per **process** (`PYTHONHASHSEED`, on by default since 3.3, a hash-collision DoS defense). Set iteration order follows hash order, so `', '.join(some_set)` yields a different string on every interpreter start. Demonstrated:

```
seed=0  -> Triumphant, Energetic, Intense, Uplifting
seed=1  -> Energetic, Triumphant, Intense, Uplifting
seed=2  -> Energetic, Triumphant, Uplifting, Intense
```

**Severity: low on its own, blocking in context.** `match_score` is unaffected — it uses `len(common)`, which is order-independent, so ranking and recommendations are correct. Only the human-readable `matched_criteria` string varies. But:

- identical `/recommend` requests can return different response bodies today, in Flask, in production
- **it breaks the only verification instrument in this plan.** Flask on :8000 and FastAPI on :8001 are two separate processes with two different hash seeds, so `matched_criteria` differs on *every* comparison — a false positive on every run, looking exactly like a migration bug

Affected sites: `song_matcher.py:92` and `song_matcher.py:100`. Verified to be the only two — every other `', '.join(...)` in the repo operates on a list from JSON, which is ordered.

### Ordering options

All one line, all deterministic, all fix the bug equally:

| Option | Code | Trade-off |
|---|---|---|
| **Alphabetical** *(recommended)* | `', '.join(sorted(common))` | Simplest, obviously correct. Ordering carries no meaning — "Aggressive" always precedes "Uplifting" for no reason |
| Song's order | `[m for m in song.get("moods") or [] if m in common]` | Preserves the ordering the song data was authored in, likely most-characteristic-first. Two songs matching the same moods may list them differently |
| Profile's order | `[m for m in desired_profile.get("moods") or [] if m in common]` | Reflects what the rule engine prioritized for *this* game. Most meaningful to a reader; consistent across all songs in one response |

Recommendation is alphabetical **for now** — not because it produces the best string (profile order does), but because of timing. This fix exists to unblock a migration diff. `sorted()` is a one-word change with no product semantics baked in; the other two change what the string *means*, which is a product decision riding along inside a migration commit. Ship determinism now, revisit semantics as its own change afterward.

`common` stays a set for `len(common)` scoring — order is imposed only at the point of display.

## Change checklist beyond the route decorators

| File | Current | Needed |
|---|---|---|
| `Dockerfile:32` | `gunicorn ... app:app` | Plain gunicorn is WSGI-only and cannot boot an ASGI app. Needs `-k uvicorn.workers.UvicornWorker`, or switch to `uvicorn` |
| `requirements.txt` | Flask, gunicorn, requests, dotenv, openai | **drifted** — `fastapi`/`uvicorn`/`pydantic` are in the venv but unrecorded, so `docker build` produces an image without them. Silent until deploy |
| `render.yml` | `FLASK_ENV=production` | vestigial after cutover |
| `docker-compose.yml` | `FLASK_ENV=production` | vestigial after cutover |
| `app.py:448,465` | `@app.errorhandler` | → `@app.exception_handler` (different signature and return type) |
| `app.py:201,271` | `app.logger.error(...)` | the only Flask coupling in lines 143–275; needs a non-Flask logger |
| `app.py` routes | `request.get_json()`, manual dict validation | → Pydantic request models. This is the real work, not boilerplate |

Endpoints to port: `GET /`, `GET /health`, `POST /recommend`, `GET /recommend/test`, `POST /webhook/recommend`.

## Environment — DECIDED

Standardize on **Python 3.13**, using `replay-rythms/`.

Install with `uv pip install "fastapi[standard]"`, keeping the `requirements.txt` workflow. `uv add` is not usable here — it requires a `pyproject.toml`, which this repo does not have. (If one is ever wanted, use `uv init --bare`; plain `uv init` scaffolds its own `main.py` and would collide with the file this plan creates.)

Docker tag notes:
- Base OS **verified** via `docker run --rm python:3.13-slim cat /etc/os-release` → `Debian GNU/Linux 13 (trixie)`, `DEBIAN_VERSION_FULL=13.6`
- **No Debian major skip.** Digest comparison confirms the old `python:3.11-slim` was *already* trixie:
  ```
  3.11-slim         -> sha256:a630a63c...
  3.11-slim-trixie  -> sha256:a630a63c...   ← identical
  3.11-slim-bookworm-> sha256:2e32f7d3...
  ```
  Exactly one variable changed: Python 3.11 → 3.13.
- The bare `-slim` suffix is a floating alias, tracking both the latest patch and the maintainers' current Debian default. Pin explicitly (`python:3.13.15-slim-trixie`) if reproducible builds matter later.

## Open questions

- **`recommend.py` (496 lines)** — Vercel serverless handler duplicating much of `app.py`'s logic. In scope for this migration, or left alone? Decide deliberately rather than by omission.
- **`working-recommend-fn/recommend.py`** — same question.
- Cutover mechanics: how long both apps run in parallel, and what triggers deleting `app.py`.

## Order of work

1. ~~Consolidate venv / Python version~~ ✅
2. ~~Install FastAPI deps~~ ✅
3. **Fix the `matched_criteria` set-ordering bug** (`song_matcher.py:92,100`) ← in progress
4. Delete `golden/` and `generate_golden_tests.py`
5. Record deps in `requirements.txt`
6. Write `main.py` — port endpoints with `def` handlers and Pydantic models
7. Run both servers, diff responses (`USE_AGENTIC=false` for exact diffs)
8. Update `Dockerfile` CMD / `docker-compose.yml` / `render.yml`
9. Cutover, remove `app.py`
