"""FastAPI wrapper + WebSocket tick stream. The prototype backend and the frozen scored endpoint.

Thin by design: all logic lives in api/service.py so it is testable without an HTTP server. The app
reads the COMMITTED REPLAY BUNDLE / reports as its data layer, so `docker compose up` on venue wifi
that does not exist still works — the demo path touches only committed artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core import paths
from core.io import read_json

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    _HAVE_FASTAPI = True

    # Request models at MODULE level, not inside create_app(). A Pydantic model defined as a local
    # class inside the factory is not reliably resolved as a request BODY by FastAPI's annotation
    # inspection — it gets treated as a query parameter, and every POST returns "field required" for
    # the whole object. Module-level is the shape FastAPI expects.
    class _LegalNextReq(BaseModel):
        partial: dict[str, str] = {}
        slot: str

    class _CompileReq(BaseModel):
        grammar_str: str

    class _AuthorReq(BaseModel):
        grammar_str: str
        view: str = "issuer"

    class _ScoreReq(BaseModel):
        event: dict
        view: str = "issuer"
except ImportError:  # pragma: no cover - the CLI degrades to a static export without FastAPI
    _HAVE_FASTAPI = False


def _report(name: str) -> Any:
    """reports/ first, then the COMMITTED REPLAY BUNDLE.

    The README promises `make api` serves the committed replay bundle, but this only ever read
    reports/ -- which is gitignored. On a fresh clone every screen rendered an error, and on a box with
    a stale smoke run the GATE screen opened with a red NOT REPORTABLE banner. The bundle fallback is
    what makes the offline demo path real rather than documented.
    """
    p = paths.reports / name
    if p.exists():
        return read_json(p)
    bundled = paths.bundles / "replay" / name
    if bundled.exists():
        payload = read_json(bundled)
        if isinstance(payload, dict):
            payload.setdefault("_served_from", "committed replay bundle (reports/ absent)")
        return payload
    return {"error": f"{name} not generated; run the relevant make target"}


def create_app():  # noqa: ANN201
    if not _HAVE_FASTAPI:
        raise RuntimeError("FastAPI is not installed. `pip install -r requirements.txt`.")
    from api.service import (
        author_attack,
        compile_attack,
        frozen_version,
        legal_next,
        morpheme_picker,
        score_one_event,
    )

    app = FastAPI(title="VAJRA", version="1.0", docs_url="/api/docs")
    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "frozen_model_version": frozen_version()}

    # ---- the six screens' data layer -------------------------------------------------
    @app.get("/api/money")
    def money() -> Any:
        return _report("money.json")

    @app.get("/api/loop")
    def loop() -> Any:
        return _report("loop_report.json")

    @app.get("/api/metrics")
    def metrics() -> Any:
        return _report("metrics_issuer.json")

    @app.get("/api/archive")
    def archive() -> Any:
        return _report("archive_report.json")

    @app.get("/api/fidelity")
    def fidelity() -> Any:
        return _report("fidelity.json")

    @app.get("/api/grammar")
    def grammar() -> Any:
        return _report("grammar_census.json")

    @app.get("/api/train")
    def train_report() -> Any:
        return _report("train_report_issuer.json")

    @app.get("/api/provenance")
    def provenance() -> Any:
        from fidelity.provenance import registry_report

        return registry_report()

    # ---- Author-an-Attack ------------------------------------------------------------
    @app.get("/api/picker")
    def picker() -> Any:
        return morpheme_picker()

    @app.post("/api/legal-next")
    def legal_next_ep(req: _LegalNextReq) -> Any:
        return {"slot": req.slot, "legal": legal_next(req.partial, req.slot)}

    @app.post("/api/compile")
    def compile_ep(req: _CompileReq) -> Any:
        return compile_attack(req.grammar_str).as_dict()

    @app.post("/api/author-attack")
    def author_ep(req: _AuthorReq) -> Any:
        # Author-an-Attack is scored against the FROZEN endpoint by construction.
        return author_attack(req.grammar_str, view=req.view)

    # ---- live scoring (GATE OPS) -----------------------------------------------------
    @app.post("/api/score")
    def score_ep(req: _ScoreReq) -> Any:
        return score_one_event(req.event, view=req.view, frozen=False)

    @app.post("/api/score-frozen")
    def score_frozen_ep(req: _ScoreReq) -> Any:
        return score_one_event(req.event, view=req.view, frozen=True)

    # ---- the tick replay stream ------------------------------------------------------
    @app.websocket("/api/ws/ticks")
    async def ws_ticks(ws: WebSocket) -> None:
        """Replay recorded ticks over WebSocket. A visible REPLAY badge is the client's job.

        Recorded, not live: the demo's primary artifact is the offline replay bundle, and a REPLAY
        badge on screen means the audience never believes something is live when it is not.
        """
        await ws.accept()
        report = _report("loop_report.json")
        ticks = (report.get("arms", {}).get("full", {}) or {}).get("ticks", [])
        try:
            await ws.send_json({"type": "meta", "n_ticks": len(ticks), "replay": True})
            for tk in ticks:
                await ws.send_json({"type": "tick", "replay": True, "data": tk})
            await ws.send_json({"type": "done", "replay": True})
        except WebSocketDisconnect:
            return

    _mount_interface(app)
    return app


# =======================================================================================
# The interface, served by this same process
# =======================================================================================

#: The interface's static export. Built with `npm run build` inside `ui/`, which emits plain HTML, CSS
#: and JavaScript with the evidence records' VALUES already baked into the markup.
_UI_DIR = paths.root / "ui" / "out"

_UI_ABSENT = """<!doctype html><meta charset=utf-8><title>VAJRA</title>
<style>body{background:#0b0b0f;color:#f2f2f5;font:15px/1.7 system-ui,sans-serif;margin:0;
padding:56px 32px}main{max-width:640px;margin:0 auto}h1{font-size:21px;margin:0 0 16px}
code{font:13px ui-monospace,monospace;color:#3dd68c;background:#15161d;padding:2px 6px;
border-radius:4px}p{color:#9a9aa8}a{color:#4a9eff}</style>
<main><h1>The interface has not been built</h1>
<p>This service is running and the API is live at <a href="/api/docs">/api/docs</a>, but the
interface's static export is absent, so there are no screens to serve.</p>
<p>Build it with <code>cd ui &amp;&amp; npm install &amp;&amp; npm run build</code>, which writes
<code>ui/out</code>, then restart this service.</p></main>"""


def _mount_interface(app: Any) -> None:
    """Serve the interface's static export from this process, so the prototype is ONE service.

    WHY THIS EXISTS. The interface and the scorer used to be two deployments with a proxy between
    them, which meant two hosts to keep alive and a base URL in the interface's build that had to name
    wherever the scorer happened to land. Serving the export from here collapses that: one process, one
    origin, one URL. The interface's client code calls `/api/...` at a relative path, so under one
    origin it reaches the routes above directly, with no proxy and no cross-origin configuration.

    ORDER MATTERS. This runs after every route above is registered. A mount at the root would
    otherwise shadow them, and every API call would be answered with the interface's markup, which
    fails in the confusing direction: a 200 carrying HTML where JSON was expected.

    A MISSING BUILD IS NOT A CRASH. If the export is absent the API still serves and the root explains
    what to run. An unbuilt interface is a normal state during development, and taking the whole
    service down for it would make the scorer untestable without Node installed.
    """
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles

    if not (_UI_DIR / "index.html").exists():
        @app.get("/", include_in_schema=False)
        def _no_interface() -> HTMLResponse:
            return HTMLResponse(_UI_ABSENT, status_code=200)
        return

    # `html=True` resolves a directory to its index, which is why the export sets `trailingSlash` and
    # emits `gate/index.html` rather than `gate.html`. Without that pairing every screen but the home
    # page is a 404 here.
    app.mount("/", StaticFiles(directory=str(_UI_DIR), html=True), name="interface")


# Uvicorn entry point: `uvicorn api.app:app`.
app = create_app() if _HAVE_FASTAPI else None
