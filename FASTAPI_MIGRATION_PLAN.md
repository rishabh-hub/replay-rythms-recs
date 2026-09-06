# Flask → FastAPI Migration

**Status: complete.** FastAPI has been serving production since deploy
`dep-daemvcdbedkc73dt8ou0` (commit `c39105f`, 2026-09-06).

Verify which app is live without reading deploy logs — `GET /health`:

| Response | App |
|---|---|
| `"timestamp":"…513709"`, keys alphabetical | Flask (`datetime.utcnow().isoformat()`) |
| `"timestamp":"…513709+00:00"`, keys insertion-ordered | **FastAPI** (current) |

## How it shipped

| Commit | Contents | Deploy |
|---|---|---|
| `428c4c1` | `main.py`, `constants.py`, `recommendation_service.py`; logic extracted out of `app.py` | not deployed alone |
| `dbcefab` | deterministic `matched_criteria`; `fastapi`/`uvicorn`/`pydantic` recorded in `requirements.txt` | live 69s, **still serving Flask** — validated Python 3.13 + trixie + new deps in isolation |
| `c39105f` | `Dockerfile` CMD → `-k uvicorn.workers.UvicornWorker main:app` | live 45s, **cutover** |

The split was deliberate: `dbcefab` changed the runtime and dependencies while
`CMD` still pointed at `app:app`, so `main.py` shipped as dead code. A failure
there could only have been the runtime. `c39105f` then changed exactly one
thing — which app serves. Rollback for the cutover is redeploying `dbcefab`.

## Architecture

`recommendation_service.py` holds `get_song_recommendation_profile`,
`get_agentic_recommendation_profile` and `get_song_recommendations`. Both
`app.py` and `main.py` import from it, so the two servers ran *identical*
business logic during the migration and any observed difference was
attributable to the web layer alone. This is what made the response diff a
usable instrument.

## Verification method

No test suite existed and `/recommend` is LLM-backed, so the instrument was a
**response diff between both apps**, run in-process rather than against two
servers:

```python
import app as flask_mod, main as fastapi_mod
from fastapi.testclient import TestClient
fc = flask_mod.app.test_client()
ac = TestClient(fastapi_mod.app, raise_server_exceptions=False)   # flag is required
```

Two traps that cost real time:

- **Flask sorts JSON keys and appends `\n`; Starlette does neither.** A
  byte-level diff reports 100% divergence on identical data. Always
  `json.loads` both sides.
- **`raise_server_exceptions=False` is mandatory.** Starlette's
  `ServerErrorMiddleware` re-raises after responding, so a default `TestClient`
  crashes instead of returning the 500 you wanted to compare.

`USE_AGENTIC` decides how deep the diff can go: `false` makes the whole path
deterministic and the full body comparable; `true` routes through the LLM and
only the contract (status, shape, keys) can be asserted.

Golden files were considered and **dropped**. First draft over-scoped them to
every pure module; `extract_data.py` is dict passthrough and `metrics.py` is
IEEE 754 float math, neither threatened by a 3.11→3.13 bump. Narrowing to
`app.py:143–275` didn't survive either — that range had two Flask touchpoints
(both `app.logger.error`), so it was a copy-paste, not a rewrite. The response
diff is a strict superset: it covers the internals *and* the route layer that
was genuinely rewritten.

## Bug found and fixed en route

`song_matcher.py` built `', '.join(some_set)`. Python randomizes string hashes
per **process**, so set iteration order — and therefore the `matched_criteria`
string — differed on every interpreter start. Identical requests returned
different bodies in Flask, in production, before this migration existed.

It also would have made the diff useless: Flask and FastAPI run as separate
processes with separate hash seeds, so every comparison would have shown a
false positive. Fixed with `sorted()` at both sites (`:92` moods, `:100`
themes).

## Accepted behaviour changes

Deliberate deviations from "change nothing observable", all verified in
production:

| Input | Flask | FastAPI | Why accepted |
|---|---|---|---|
| `{"top_n": null}` | 200, returns **all 39 songs** | 400 | `scored[:None]` slicing the whole catalogue is an accident, not a contract. Matching it needs `top_n: Any` and would enshrine the bug |
| `HEAD` / `OPTIONS` any route | 200 | 405 | FastAPI's `APIRoute` doesn't auto-add `HEAD`. Render's healthcheck uses GET; only matters for HEAD-based uptime probes |
| `?player_id=a&player_id=b` | first value | last value | Starlette's `QueryParams.get` semantics. Silent wrong answer, low likelihood |
| `NaN` / `Infinity` in results | 200 with invalid JSON | 500 | Reachable via crafted `replay_data`. FastAPI is arguably more correct — bare `NaN` is not valid JSON |
| `?top_n=abc` | 500 | 400 | Pydantic rejects before the handler. Improved status class |

Preserved on purpose: `/recommend/test` returns 200 even when
`result["success"]` is false; `/webhook/recommend` wraps failures as
`200 {"success":true,"result":{…}}`; `datetime.utcnow()` kept despite
deprecation; the dead `callback_url` TODO kept.

`callback_url` is typed `Any`, not `str | None` — Flask discarded it untyped,
so a stricter type 422'd requests Flask answered 200.

## Design decisions

**Handlers are `def`, not `async def`.** `get_song_recommendations` does
blocking file I/O (`song_management.py:29`) and, when `USE_AGENTIC=true`, a
synchronous OpenAI call (`game_analyst.py:189`). FastAPI runs `def` handlers in
a threadpool but `async def` on the event loop — `async` here would stall every
concurrent request. `/` and `/health` are `async def`: no I/O, which is the
exception the FastAPI docs carve out. Async is not a win until the I/O beneath
it is awaitable.

**`FastAPI(redirect_slashes=False, docs_url=None, redoc_url=None,
openapi_url=None)`.** Flask 404s on a trailing slash where Starlette would
307-redirect, and Flask serves no docs routes. Under "change nothing
observable", `/docs` and `/openapi.json` are observable.

**One `RequestValidationError` handler** returning Flask's
`400 {"success": false, "error": "Request must be JSON"}`, rather than
per-field workarounds. FastAPI validates before the handler runs, so Flask's
hand-rolled 400s became 422s across the board; one handler restores the
contract everywhere.

**`JSONResponse` everywhere, not bare dicts.** Bare dicts go through
`jsonable_encoder`, which silently coerces an unserializable object to `{}`;
`JSONResponse` uses `json.dumps` and fails loudly like Flask. Mixing the two
across endpoints meant identical failures behaved differently per route.

## Deployment notes

- `dockerCommand` is empty on the Render service, so the **Dockerfile `CMD`
  governs** — no dashboard override to reconcile.
- The exec-form `CMD` must be valid JSON. A missing comma silently degrades it
  to shell form and the container won't start as intended.
- `python:3.11-slim` was *already* trixie — digest comparison confirmed
  `3.11-slim` == `3.11-slim-trixie`. The bump to 3.13 changed one variable, not
  two.
- Deploys are manual. `autoDeploy` reads `yes` but has never fired; production
  sat on a February commit for seven months. Don't assume push means deploy.
- Free plan, `numInstances: 1` — no blue/green. The in-process diff is the only
  pre-deploy gate.

## Remaining cleanup

- [x] Delete `app.py` — dead since `c39105f`. Also collapses the duplicate
      `FULL_REPLAY_DATA_SAMPLE` in `app.py:18` / `constants.py:1`
- [x] Drop `Flask` from `requirements.txt` (keep `gunicorn` — still the process manager)
- [ ] Remove `FLASK_ENV=production` from `render.yml` and the dashboard
- [x] Delete the stale scaffolding comment at `main.py:1-5` and the dead
      `USE_AGENTIC` line (the live one is in `recommendation_service.py`)
- [ ] Swap `uvicorn.workers.UvicornWorker` → the `uvicorn-worker` package to
      clear the boot-time deprecation warning
- [ ] `recommend.py` (496 lines, Vercel handler) and
      `working-recommend-fn/recommend.py` still duplicate the pipeline —
      never brought into scope, decide deliberately
- [ ] `def` → `async def` once `game_analyst.py` uses `AsyncOpenAI`. That is
      when FastAPI starts paying for itself
