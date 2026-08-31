"""The WHOLE prototype, as a single Hugging Face Space: the interface and the scorer.

WHY NOT DOCKER. The Docker SDK is a paid tier on this account, so the Space is created under the
Gradio SDK. That only determines which base image runs; it does not oblige the application to be a
Gradio app.

WHY GRADIO IS NOT IMPORTED. It was, and it broke twice. A Space exposes one port and runs this file;
anything listening on that port is served. The application is already FastAPI, so it binds the port
itself and Gradio is not in the path at all.

The specific failure worth recording, because it is the kind that recurs: the base image ships
`huggingface_hub` 1.x, which removed `HfFolder`, while a pinned Gradio 4.44 still imports that symbol
in its OAuth module. The versions are set by two different parties and there is no combination this
file can assert that keeps them agreeing. Removing the dependency removes the class of bug, and costs
nothing here because the landing page is nine lines of HTML.

WHY THE CODE IS FETCHED AT STARTUP. Without a Dockerfile there is no build step, so there is nowhere
to clone from except the running process. The checkout is sparse and blob-filtered over only the paths
the scorer opens: ~145 MB rather than the repository's ~650 MB, because the model directory holds
eight bundles and the issuer view resolves to exactly one of them, the promoted fusion weights being
the supervised channel alone.

THE COST, STATED PLAINLY. A free Space stops when idle and its disk does not survive that, so the
fetch runs again on each wake and adds roughly half a minute before anything is served.

WHY ROOT RESOLUTION NEEDS NO PATCHING. The package derives its own root from the location of its path
module rather than from the working directory, so dropping the tree anywhere and putting it on the
import path is sufficient.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

REPO = "https://github.com/EISHKARAN/Hackathon-MasterCard.git"
REF = "main"
PORT = 7860
HERE = pathlib.Path(__file__).resolve().parent
CHECKOUT = HERE / "_checkout"
TREE = CHECKOUT / "vajra"

#: Only what the scorer opens.
#:
#: DIRECTORIES ONLY. `sparse-checkout set` defaults to cone mode, which rejects a file path outright:
#: naming `vajra/requirements.txt` here failed the whole checkout with "is not a directory". It is also
#: unnecessary, because cone mode already includes the loose files sitting in each listed path's parent
#: directories, so everything directly inside `vajra/` arrives by virtue of `vajra/api` being listed.
SPARSE = [
    "vajra/api", "vajra/archive", "vajra/attack", "vajra/bench", "vajra/config", "vajra/core",
    "vajra/eval", "vajra/features", "vajra/fidelity", "vajra/gate", "vajra/generator_b",
    "vajra/governance", "vajra/grammar", "vajra/loop", "vajra/scripts", "vajra/sim",
    "vajra/bundles", "vajra/reports", "vajra/ui/out",
    "vajra/data/models/gate-i_issuer",
]


def fetch() -> None:
    if (TREE / "core" / "paths.py").exists():
        print("scorer tree already present, skipping fetch", flush=True)
        return
    # A checkout that exists without that file is a PARTIAL one: the clone succeeded and the sparse
    # step then failed, which is exactly what a bad path in SPARSE produces. Left in place it turns the
    # next attempt into "destination path already exists", a different error that hides the real cause.
    if CHECKOUT.exists():
        print("removing an incomplete checkout from a previous attempt", flush=True)
        shutil.rmtree(CHECKOUT, ignore_errors=True)
    print(f"fetching {REF} from {REPO} ...", flush=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse",
         "--branch", REF, REPO, str(CHECKOUT)],
        check=True,
    )
    subprocess.run(["git", "-C", str(CHECKOUT), "sparse-checkout", "set", *SPARSE], check=True)
    print("fetch complete", flush=True)


fetch()
sys.path.insert(0, str(TREE))

import uvicorn  # noqa: E402  (imported after the tree is on the path)
# Importing this builds the application, which mounts the interface's static export at the root
# and keeps every /api route ahead of it. One import, both halves.
from api.app import app  # noqa: E402

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
