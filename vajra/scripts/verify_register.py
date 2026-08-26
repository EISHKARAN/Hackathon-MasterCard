"""`make verify` — scan the repo for [VERIFY] markers and render VERIFY_REGISTER.md.

The design's posture: 25 [VERIFY] markers are 25 verifiable claims we REFUSED TO FAKE, each naming the
primary source that settles it, against a field that would state the same claims as fact without
checking. This target counts them so the register cannot silently drift from the code.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path
from core import paths
from core.io import write_json
from core.stagelog import stage

_RX = re.compile(r"\[VERIFY[^\]]*\]")
_EXTS = {".py", ".yaml", ".yml", ".md"}
_SKIP = {"VERIFY_REGISTER.md"}


def main() -> int:
    paths.ensure_writable()
    with stage("verify") as summary:
        hits: list[dict] = []
        for p in sorted(paths.root.rglob("*")):
            if p.suffix not in _EXTS or p.name in _SKIP:
                continue
            if any(part in {".venv", ".git", "node_modules", "data", "reports"} for part in p.parts):
                continue
            for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if _RX.search(line):
                    hits.append({"file": str(p.relative_to(paths.root)), "line": i,
                                 "text": " ".join(line.strip().split())[:200]})
        print(f"\n=== VAJRA [VERIFY] REGISTER ===\n  {len(hits)} markers across the repo")
        write_json({"n_markers": len(hits), "markers": hits}, paths.reports / "verify_register.json")
        # Render the committed register.
        lines = ["# VERIFY_REGISTER.md",
                 "",
                 "Every `[VERIFY]` marker in the repo. Each is a verifiable claim we REFUSED TO FAKE,",
                 "against a field that would state the same claim as fact without checking. Not knowing",
                 "is not the failure; asserting is.",
                 "",
                 f"**{len(hits)} markers.** Machine-counted by `make verify`.",
                 "",
                 "| File | Line | Claim |", "|---|---|---|"]
        for h in hits:
            lines.append(f"| {h['file']} | {h['line']} | {h['text'].replace('|','\\|')} |")
        (paths.root / "VERIFY_REGISTER.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"  wrote VERIFY_REGISTER.md and reports/verify_register.json")
        summary.update({"n_markers": len(hits)})
    return 0


if __name__ == "__main__":
    sys.exit(main())
