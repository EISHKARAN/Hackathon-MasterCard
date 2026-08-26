"""`make bundle` — assemble the committed OFFLINE REPLAY BUNDLE, the primary demo artifact.

The design's demo is offline-first: a live LLM call or network dependency at a venue is a single point
of failure, and losing the demo costs more than the live path buys. So the bundle carries every report
and artifact the six screens read, plus a manifest with a content hash, and the API serves from it with
no network access and no model training.
"""
from __future__ import annotations
import json, shutil, sys
from core import paths
from core.io import sha256_file, write_json
from core.stagelog import stage

# What the six screens read. Missing files are noted, not fabricated.
BUNDLE_REPORTS = [
    "money.json", "loop_report.json", "metrics_issuer.json", "archive_report.json",
    "fidelity.json", "fidelity.html", "grammar_census.json", "bench.json",
    "verify_register.json", "duallog.json", "report.md",
]


def main() -> int:
    paths.ensure_writable()
    with stage("bundle") as summary:
        out = paths.bundles / "replay"
        out.mkdir(parents=True, exist_ok=True)
        manifest = {"files": [], "missing": []}
        for name in BUNDLE_REPORTS:
            src = paths.reports / name
            if src.exists():
                dst = out / name
                shutil.copy2(src, dst)
                manifest["files"].append({"name": name, "sha256": sha256_file(dst)})
            else:
                manifest["missing"].append(name)
        # The dual-use reject log is a governance artifact that ships with the bundle.
        gov = paths.governance / "dual_use_reject_log.json"
        if gov.exists():
            shutil.copy2(gov, out / "dual_use_reject_log.json")
            manifest["files"].append({"name": "dual_use_reject_log.json", "sha256": sha256_file(out / "dual_use_reject_log.json")})
        manifest["n_files"] = len(manifest["files"])
        manifest["note"] = (
            "The OFFLINE replay bundle: the primary demo artifact. The UI serves these committed "
            "files with no network access and no model training, so a venue with no wifi still works. "
            "Any live run is a bonus with a visible REPLAY badge."
        )
        write_json(manifest, out / "manifest.json")
        print(f"  bundle: {out.relative_to(paths.root)}  ({manifest['n_files']} files)")
        if manifest["missing"]:
            print(f"  missing (run their targets first): {manifest['missing']}")
        summary.update({"n_files": manifest["n_files"], "n_missing": len(manifest["missing"])})
    return 0


if __name__ == "__main__":
    sys.exit(main())
