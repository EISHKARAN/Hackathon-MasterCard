/** @type {import('next').NextConfig} */

module.exports = {
  reactStrictMode: true,

  // A STATIC EXPORT, so the whole prototype is ONE service.
  //
  // The interface used to need its own Node server, which meant deploying two things and keeping a
  // proxy between them pointed at whichever host the other one landed on. Exporting to plain files
  // removes the second service entirely: the scorer serves these files itself, and there is no Node
  // process at runtime at all.
  //
  // WHAT THIS COSTS. The five evidence screens are rendered at BUILD time rather than per request, so
  // they are a snapshot of the records as they stood when the build ran. That is the right trade here,
  // because the records are committed artefacts of a finished pipeline run rather than live data. The
  // consequence worth remembering: re-running the pipeline means rebuilding the interface, or the
  // screens keep showing the previous run's numbers.
  //
  // WHAT IT DOES NOT COST. Authoring an attack still works. That screen's picker is a client component
  // calling the scorer at a relative path, and under one service that path is the same origin, so it
  // needs no proxy and no cross-origin configuration.
  output: "export",

  // Emits `gate/index.html` rather than `gate.html`, which is what lets a plain static file server
  // resolve `/gate` by looking for a directory index. Without it every screen except the home page
  // returns 404 once served by something other than Next.
  trailingSlash: true,

  // NO `rewrites` BLOCK, and no output-tracing block either. Static export supports neither, and
  // neither is needed any more. The rewrite existed only to bridge two separate services. The tracing
  // directive existed to carry the evidence records into a serverless bundle; with an export the
  // records are read at build time and their VALUES are baked into the HTML, so nothing needs to
  // travel to a runtime that no longer exists.
  //
  // The prebuild staging step still matters: it is what puts the records where the build can read them.
};
