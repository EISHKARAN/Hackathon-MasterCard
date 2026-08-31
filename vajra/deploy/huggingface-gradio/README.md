---
title: VAJRA Scorer
emoji: 🛡️
colorFrom: red
colorTo: blue
sdk: gradio
sdk_version: 4.44.0
app_file: app.py
pinned: false
license: mit
short_description: Compiles, executes and scores authored payment-fraud attacks
---

# VAJRA Scorer

The scoring service behind the VAJRA interface. It compiles an authored attack composition against a
typed six-slot grammar, executes it in the payment simulator, passes it through the rail invariant
gate, and scores it with the promoted detection model.

This Space serves an API. The interface that consumes it is deployed separately.

## Routes

| route | purpose |
|---|---|
| `GET /api/picker` | the six grammar slots and their legal values |
| `POST /api/legal-next` | given a partial composition, which values still type-check |
| `POST /api/author-attack` | compile, execute, gate, score, and return the decision trace |
| `GET /api/docs` | generated API reference |

## What it is not

No training, no data generation, no network egress while serving. Compositions come from a committed
cache and scoring uses the already-promoted model bundle, so the latency it reports is the real thing
rather than a warm-up artefact.

Authored attacks are novel **within** a fixed grammar. They are not attack categories outside it, and
the interface says so on the screen where you compose one.

## Free-tier behaviour

The Space stops when idle. On wake it re-fetches the scorer's code and its model bundle, which adds
roughly half a minute to the first request. The interface treats an unreachable scorer as an expected
condition: the live composer shows a notice and the five evidence screens, which read committed
records directly, are unaffected.
