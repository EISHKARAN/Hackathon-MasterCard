/* Copy the evidence records INTO the interface tree before the build.
 *
 * WHY THIS IS NECESSARY. The read-only screens render on the server by reading the evidence JSON from
 * disk. On a serverless host that works only if the files are inside the deployed tree, because the
 * repository root does not exist on the filesystem at request time. The interface directory is the
 * deployment root, so `../reports` is reachable during the BUILD but gone at RUNTIME.
 *
 * Staging them here, plus the tracing directive in the Next config, is what carries them across that
 * boundary. Without both, every screen renders its absent-artefact fallback and the deployment looks
 * like a broken pipeline rather than a path that was never wired up.
 *
 * The staged directory is generated, so it is git-ignored: the evidence is already committed once at
 * the repository root and a second copy in history would be pure duplication.
 *
 * PRECEDENCE. The replay bundle is copied first and the live evidence directory second, so a record
 * present in both wins from the evidence directory. That matches the loader's own search order, and
 * it means a stale bundled copy can never shadow a fresher measured one.
 */
import fs from "node:fs";
import path from "node:path";

const HERE = path.dirname(new URL(import.meta.url).pathname);
const UI = path.resolve(HERE, "..");
const REPO = path.resolve(UI, "..");
const DEST = path.join(UI, "reports");

const SOURCES = [path.join(REPO, "bundles", "replay"), path.join(REPO, "reports")];

/* AN ALLOWLIST, NOT EVERY RECORD IN THE DIRECTORY.
 *
 * Copying the whole directory staged 54 MB, of which 30 MB no screen ever opens: per-view training
 * records, the dual-use rejection log, scratch probes. Everything staged is carried into the
 * serverless bundle, so an unread record is pure deployment weight.
 *
 * These are the records the six screens read, plus the ones the home screen's fallback panel reports
 * on when a record is genuinely absent. That panel has to be able to distinguish "absent" from
 * "present but not staged", so its whole list is staged too, otherwise it would report a record as
 * missing when it exists at the repository root.
 */
const WANTED = new Set([
  "money.json",                  // economics
  "metrics_issuer.json",         // results, and the author screen's generalisation figures
  "grammar_census.json",         // attack space, and the author screen's legal-composition counts
  "archive_report.json",         // attack space coverage
  "fidelity.json",               // the invariant gate
  "sim_report_vajra-sim.json",   // generated volume and realised attack share
  "loop_report.json",            // the loop. 23 MB, and the only large record in the set
  "train_report_issuer.json",    // the fallback panel's inventory
]);

fs.mkdirSync(DEST, { recursive: true });

// Keyed by filename, so a record present in BOTH sources is counted once at its final size rather
// than once per copy. The earlier version added bytes per copy and reported 47 MB for 24 MB of files.
const staged = new Map();

for (const src of SOURCES) {
  if (!fs.existsSync(src)) {
    console.log(`  stage-reports: ${path.relative(REPO, src)} absent, skipping`);
    continue;
  }
  for (const f of fs.readdirSync(src)) {
    // Only the machine-readable records the screens actually open. Rendered bodies are formatted
    // views rather than evidence, and scratch probes are not reportable and must never reach a screen
    // that presents numbers as measured.
    if (!WANTED.has(f)) continue;
    const to = path.join(DEST, f);
    fs.copyFileSync(path.join(src, f), to);
    staged.set(f, fs.statSync(to).size);
  }
}

const copied = staged.size;
const bytes = [...staged.values()].reduce((a, b) => a + b, 0);
const missing = [...WANTED].filter((w) => !staged.has(w));

console.log(`  stage-reports: ${copied} of ${WANTED.size} records staged into ui/reports `
            + `(${(bytes / 1048576).toFixed(1)} MB)`);
// Named individually rather than counted. A screen whose record is absent renders its fallback, and
// knowing WHICH one at build time is the difference between a one-line fix and hunting at runtime.
for (const m of missing) console.log(`  stage-reports: MISSING ${m} - its screen will render empty`);

// A build that silently stages nothing produces a deployment where every screen says the pipeline has
// not run. Failing here instead makes the cause obvious at build time, where it is cheap to fix.
if (copied === 0) {
  console.error("  stage-reports: NO records found. The screens would all render empty.");
  process.exit(1);
}
