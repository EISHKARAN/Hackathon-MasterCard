# The scorer, as a Hugging Face Docker Space.
#
# WHY THIS IS TEN LINES INSTEAD OF AN AFTERNOON. The image clones the public repository at build time,
# which already carries the promoted model bundles and the evidence records. There is nothing to
# upload into the Space, no Git LFS to configure, and no second copy of a 600 MB artefact to keep in
# sync. Publishing the bundles to the public repository is what buys that.
#
# WHY A SPACE RATHER THAN A SMALL CONTAINER HOST. The scorer loads a gradient-boosted model, a
# conformal calibration table and a rank calibrator. Free tiers elsewhere cap at 512 MB of memory,
# which this does not reliably fit inside. A Space gets 16 GB, so memory stops being a design
# constraint.
#
# WHAT IT DOES NOT DO. No training, no data generation, no network egress at request time. It scores
# authored compositions against the already-promoted bundle and serves the grammar's type checker.

FROM python:3.13-slim

# git to fetch the repository. libgomp1 is LightGBM's OpenMP runtime: without it the import fails at
# request time with a bare "libgomp.so.1: cannot open shared object file", which reads as a code fault
# rather than a missing system library.
RUN apt-get update && apt-get install -y --no-install-recommends git libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# A non-root user, because Spaces run unprivileged and a root-owned tree is not writable at runtime.
RUN useradd -m -u 1000 vajra
USER vajra
ENV HOME=/home/vajra PATH=/home/vajra/.local/bin:$PATH
WORKDIR $HOME/app

# Shallow, single-branch clone. The repository carries the model bundles, so this is the large step;
# depth 1 keeps it to the tip rather than the whole history.
ARG REPO=https://github.com/EISHKARAN/Hackathon-MasterCard.git
ARG REF=main
RUN git clone --depth 1 --branch $REF $REPO /tmp/repo \
 && cp -r /tmp/repo/vajra/. . \
 && rm -rf /tmp/repo

RUN pip install --no-cache-dir --user -r requirements.txt

# The demo path never reaches the network: compositions are served from the committed cache rather
# than generated, which is what makes the scoring reproducible and the latency honest.
ENV LLM_MODE=cached \
    VAJRA_PRESET=small \
    PYTHONUNBUFFERED=1

# 7860 is the port a Space exposes. It must match `app_port` in the Space's own README.
EXPOSE 7860
CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "7860"]
