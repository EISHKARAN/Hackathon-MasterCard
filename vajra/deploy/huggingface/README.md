---
title: VAJRA Scorer
emoji: 🛡️
colorFrom: red
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# VAJRA Scorer

The scoring service behind the VAJRA interface. It compiles an authored attack composition against a
typed six-slot grammar, executes it in the payment simulator, passes it through the rail invariant
gate, and scores it with the promoted detection model.

This Space serves an API, not a page. The interface that consumes it is deployed separately.

## What it exposes

| route | purpose |
|---|---|
| `GET /api/picker` | the six grammar slots and their legal values |
| `POST /api/legal-next` | given a partial composition, which values still type-check |
| `POST /api/author-attack` | compile, execute, gate, score, and return the decision trace |
| `GET /api/docs` | the generated API reference |

## What it is not

It does not train anything, generate data, or reach the network while serving. Compositions come from
a committed cache and scoring uses the already-promoted model bundle, so the latency it reports is the
real thing rather than a warm-up artefact.

Attack compositions are novel **within** a fixed grammar. They are not attack categories outside it,
and the interface says so on the screen where you compose one.

## Free-tier behaviour

A free Space sleeps after a period of inactivity and takes roughly half a minute to wake. The
interface treats an unreachable scorer as an expected condition: the live composer shows a notice and
the five evidence screens, which read committed records directly, are unaffected.
