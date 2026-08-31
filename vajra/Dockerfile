# VAJRA, as ONE service.
#
# Build context is this directory:   docker build -t vajra .
# Run:                              docker run -p 8080:8080 vajra
#
# WHAT THIS PRODUCES. A single container serving six screens and the scoring API behind them, on one
# port, one origin. No Node at runtime, no second service, no proxy, and no base URL that has to name
# wherever a companion service happened to land.
#
# WHY TWO STAGES. The interface is a static export: Node is needed to BUILD it and irrelevant
# afterwards. Compiling it in a throwaway stage and copying only the output keeps the runtime image
# Python-only, and drops roughly 400 MB of toolchain that would otherwise ship for no reason.
#
# A USEFUL CONSEQUENCE. The export is rebuilt from source on every image build, so the image can never
# ship a stale one. The copy committed at ui/out exists for hosts that cannot run a build step; here it
# is ignored and regenerated.

# =======================================================================================
# Stage 1 - compile the interface to static files
# =======================================================================================
FROM node:20-slim AS interface
WORKDIR /build

# Dependencies first, and separately from the source, so editing a screen does not invalidate the
# install layer. This is the difference between a 20-second rebuild and a three-minute one.
COPY ui/package.json ui/package-lock.json* ./ui/
RUN cd ui && (npm ci --no-audit --no-fund || npm install --no-audit --no-fund)

# The evidence records must be present BEFORE the build, not after. The screens are rendered at build
# time and the records' values are baked into the markup, so the prebuild step stages them and the
# build reads them. Without these two directories every screen renders its absent-artefact fallback
# and the failure only shows up in the browser.
COPY reports ./reports
COPY bundles ./bundles
COPY ui ./ui

RUN cd ui && npm run build

# Fail the build here rather than shipping an image whose screens are all empty. A missing export is
# cheap to diagnose now and expensive to diagnose in a deployment log.
RUN test -f ui/out/index.html || (echo "the interface export is missing" && exit 1)

# =======================================================================================
# Stage 2 - the service
# =======================================================================================
FROM python:3.13-slim

# libgomp1 is LightGBM's OpenMP runtime. Without it the import fails at request time with a bare
# "libgomp.so.1: cannot open shared object file", which reads as a code fault rather than a missing
# system library.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Again dependencies before source, so a code change does not reinstall numpy, polars, duckdb,
# lightgbm and scikit-learn.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# The application. What is EXCLUDED here matters as much as what is included: see .dockerignore, which
# keeps out the 1.1 GB event stream, the intermediate caches, and seven of the eight model bundles.
COPY . .

# Only the built output crosses from stage 1. Its node_modules and .next do not.
COPY --from=interface /build/ui/out ./ui/out

# The demo path never reaches the network: compositions come from the committed cache rather than being
# generated, which is what makes the scoring reproducible and the reported latency honest.
ENV LLM_MODE=cached \
    VAJRA_PRESET=small \
    PYTHONUNBUFFERED=1 \
    PORT=8080

EXPOSE 8080

# $PORT is honoured because most hosts inject it and route to it; a hardcoded port produces a service
# that builds cleanly and then fails every health check. The shell form is required for the variable to
# expand at all - the exec form would pass the literal string "${PORT}" to uvicorn.
CMD ["sh", "-c", "exec uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8080}"]
