// Formatting helpers. The `score` one is load-bearing: a real fused score of 2.175e-12 must NOT
// render as "0.0000" and look like a broken model — a previous build spent a debugging session on a
// model that was working correctly and displaying wrongly. Below the display precision we switch to
// scientific notation so a tiny-but-nonzero score reads as tiny-but-nonzero.

export function score(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  if (x === 0) return "0";
  const abs = Math.abs(x);
  if (abs < 1e-4) return x.toExponential(2); // scientific, so a real 2.2e-12 is visible
  return x.toFixed(4);
}

export function pct(x: number | null | undefined, digits = 1): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  return (x * 100).toFixed(digits) + "%";
}

export function rupees(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  // Indian grouping (lakh/crore) reads right to a payments-in-India audience.
  return "₹" + Math.round(x).toLocaleString("en-IN");
}

export function num(x: number | null | undefined): string {
  if (x === null || x === undefined || Number.isNaN(x)) return "n/a";
  return Math.round(x).toLocaleString("en-IN");
}
