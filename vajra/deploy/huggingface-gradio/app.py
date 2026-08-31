"""The scorer, as a Hugging Face Gradio Space.

WHY GRADIO AND NOT DOCKER. The Docker SDK is a paid tier on this account. Gradio runs on FastAPI, so
the existing scorer mounts into it unchanged: no rewrite, no second API surface, and the routes the
interface already calls keep their paths.

WHY THE CODE IS FETCHED AT STARTUP RATHER THAN COMMITTED HERE. Without a Dockerfile there is no build
step, so there is nowhere to clone from except the running process. The alternative is committing 145
MB of model bundle and evidence into this Space with Git LFS, which is more reliable at runtime but a
second copy to keep in sync. The fetch is a sparse, blob-filtered checkout of only the paths the
scorer opens, so it pulls ~145 MB rather than the repository's full ~650 MB.

THE COST, STATED PLAINLY. A free Space stops when idle and its disk does not survive that, so the
fetch runs again on each wake and adds roughly half a minute on top of the wake itself. The interface
treats an unreachable scorer as expected: the live composer shows a notice and the five evidence
screens, which read committed records directly, are unaffected. A second attempt succeeds.

WHY ROOT RESOLUTION NEEDS NO PATCHING. The package derives its own root from the location of its path
module rather than from the working directory, so dropping the tree anywhere and putting it on the
import path is sufficient.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = "https://github.com/EISHKARAN/Hackathon-MasterCard.git"
REF = "main"
HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE / "_checkout"
TREE = CHECKOUT / "vajra"

#: Only what the scorer opens. Listing paths individually is what keeps the fetch at 145 MB: the model
#: directory holds eight bundles totalling 628 MB, and the scorer resolves the issuer view to exactly
#: one of them because the promoted fusion weights are g1 alone.
SPARSE = [
    "vajra/api", "vajra/archive", "vajra/attack", "vajra/bench", "vajra/config", "vajra/core",
    "vajra/eval", "vajra/features", "vajra/fidelity", "vajra/gate", "vajra/generator_b",
    "vajra/governance", "vajra/grammar", "vajra/loop", "vajra/scripts", "vajra/sim",
    "vajra/bundles", "vajra/reports", "vajra/requirements.txt",
    "vajra/data/models/gate-i_issuer",
]


def fetch() -> None:
    if (TREE / "core" / "paths.py").exists():
        print("scorer tree already present, skipping fetch")
        return
    print(f"fetching {REF} from {REPO} ...")
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
         "--branch", REF, REPO, str(CHECKOUT)],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(CHECKOUT), "sparse-checkout", "set", *SPARSE],
        check=True,
    )
    print("fetch complete")


fetch()
sys.path.insert(0, str(TREE))

import gradio as gr  # noqa: E402  (import after the tree is on the path)
import uvicorn  # noqa: E402

from api.app import app as scorer  # noqa: E402  the existing FastAPI app, unmodified

LANDING = """
### VAJRA Scorer

This Space serves an **API**, not a page. It compiles an authored attack composition against a typed
six-slot grammar, executes it in the payment simulator, passes it through the rail invariant gate, and
scores it with the promoted detection model.

| route | purpose |
|---|---|
| `GET /api/picker` | the six grammar slots and their legal values |
| `POST /api/legal-next` | given a partial composition, which values still type-check |
| `POST /api/author-attack` | compile, execute, gate, score, return the decision trace |
| `GET /api/docs` | generated API reference |

Nothing here trains or generates data. Compositions come from a committed cache and scoring uses the
already-promoted bundle, so the reported latency is real rather than a warm-up artefact.

Authored attacks are novel **within** a fixed grammar, not attack categories outside it.
"""

with gr.Blocks(title="VAJRA Scorer", analytics_enabled=False) as demo:
    gr.Markdown(LANDING)

# Gradio mounts at the root so the Space has a landing page. The scorer's own routes were registered
# on the application before this call, and a route registered directly always takes precedence over a
# later mount, so /api/* continues to resolve to the scorer rather than to Gradio.
app = gr.mount_gradio_app(scorer, demo, path="/")

if __name__ == "__main__":
    # 7860 is the port a Space exposes.
    uvicorn.run(app, host="0.0.0.0", port=7860)
