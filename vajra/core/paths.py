"""Filesystem layout, resolved from the repo root rather than the cwd.

Every path in VAJRA goes through here. The reason is not tidiness: `make` targets,
pytest, the FastAPI app and the UI's backend all start from different working
directories, and a relative path that works in one breaks in another. Resolving from
this module's own location makes the layout independent of the caller.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Paths:
    """Resolved repo layout.

    `data` and `reports` are the only two roots that are written to during a run;
    everything else is read-only committed material. VAJRA_DATA_DIR / VAJRA_REPORTS_DIR
    relocate them so a judge can run against a read-only checkout.
    """

    root: Path

    # --- committed, read-only ---------------------------------------------------
    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def grammar(self) -> Path:
        return self.root / "grammar"

    @property
    def features(self) -> Path:
        return self.root / "features"

    @property
    def governance(self) -> Path:
        return self.root / "governance"

    @property
    def bundles(self) -> Path:
        return self.root / "bundles"

    @property
    def corpora(self) -> Path:
        return self.root / "attack" / "corpora"

    @property
    def composer_cache(self) -> Path:
        return self.root / "attack" / "cache"

    @property
    def docs(self) -> Path:
        return self.root / "docs"

    # --- generated --------------------------------------------------------------
    @property
    def data(self) -> Path:
        override = os.environ.get("VAJRA_DATA_DIR")
        return Path(override).resolve() if override else self.root / "data"

    @property
    def reports(self) -> Path:
        override = os.environ.get("VAJRA_REPORTS_DIR")
        return Path(override).resolve() if override else self.root / "reports"

    @property
    def events(self) -> Path:
        return self.data / "events"

    @property
    def labels(self) -> Path:
        return self.data / "labels"

    @property
    def models(self) -> Path:
        return self.data / "models"

    @property
    def artifacts(self) -> Path:
        return self.data / "artifacts"

    @property
    def loop_state(self) -> Path:
        return self.data / "loop"

    @property
    def figures(self) -> Path:
        return self.reports / "figures"

    def ensure_writable(self) -> None:
        """Create the generated roots. Idempotent, and the only mkdir in the repo."""
        for p in (
            self.data,
            self.reports,
            self.events,
            self.labels,
            self.models,
            self.artifacts,
            self.loop_state,
            self.figures,
        ):
            p.mkdir(parents=True, exist_ok=True)


paths = Paths(root=_REPO_ROOT)
