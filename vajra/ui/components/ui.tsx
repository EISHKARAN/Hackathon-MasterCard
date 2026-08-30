/* Shared presentation components.
 *
 * WHY THESE EXIST. Every screen was re-implementing "a number with its denominator", "a provenance
 * badge", "a caveat" — and they drifted, which on this project is worse than ugly: a metric shown
 * without its denominator or its provenance tier is exactly the kind of claim the whole design
 * refuses to make. These centralise the pattern so a technicality cannot be dropped by accident.
 *
 * Nothing here fetches or transforms data. Presentation only.
 */
"use client";
import { CSSProperties, ReactNode } from "react";

type Tone = "blue" | "green" | "red" | "amber" | "purple";

/* ---------------------------------------------------------------- Kicker + section headers -- */
export function Kicker({ children, tone = "blue" }: { children: ReactNode; tone?: Tone }) {
  return <div className={`kicker ${tone}`}>{children}</div>;
}

/** A numbered step. The flow on AUTHOR-AN-ATTACK *is* the argument, so it gets real furniture. */
export function Step({ n, title, tone = "blue" }: { n: number | string; title: string; tone?: Tone }) {
  return (
    <div className={`step ${tone}`}>
      <span className="n">{n}</span>
      <h2>{title}</h2>
      <span className="rule" />
    </div>
  );
}

/* ---------------------------------------------------------------- KPI ----------------------- */
/**
 * A headline number. `denom` is NOT optional by convention: a number without its denominator is
 * the single most common way a fraud metric misleads, so the prop is always passed even when the
 * denominator is "of N scored events".
 */
export function Kpi({
  label, value, denom, tone = "blue", note,
}: { label: string; value: ReactNode; denom?: ReactNode; tone?: Tone; note?: ReactNode }) {
  return (
    <div className={`panel kpi ${tone}`}>
      <div className="label">{label}</div>
      <div className={`stat ${tone}`}>{value}</div>
      {denom && <div className="denom">{denom}</div>}
      {note && <div className="why">{note}</div>}
    </div>
  );
}

/* ---------------------------------------------------------------- badges -------------------- */
export function Badge({ kind, children }: { kind: string; children: ReactNode }) {
  return <span className={`badge ${kind}`}>{children}</span>;
}

/** Provenance tier. T1 = measured here, T2 = derived, T3 = design-only. Never silently omitted. */
export function Tier({ tier }: { tier: string | number }) {
  const t = String(tier).toLowerCase().replace("t", "");
  const label = t === "1" ? "T1 MEASURED" : t === "2" ? "T2 DERIVED" : "T3 DESIGN-ONLY";
  return <span className={`badge t${t}`}>{label}</span>;
}

export function Pill({ band }: { band: string }) {
  return <span className={`pill ${band}`}>{band.replace(/_/g, " ")}</span>;
}

/* ---------------------------------------------------------------- technicalities strip ------ */
/**
 * The dense monospaced strip that carries model pins, thresholds, denominators and latencies.
 * Pass pairs; a null value is dropped rather than rendered as "undefined".
 */
export function Tech({ items }: { items: Array<[string, ReactNode] | null | false> }) {
  const kept = items.filter(Boolean) as Array<[string, ReactNode]>;
  if (!kept.length) return null;
  return (
    <div className="tech">
      {kept.map(([k, v], i) => (
        <span key={k + i} className="row" style={{ gap: 6 }}>
          <span className="k">{k}</span>
          <span className="v">{v}</span>
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- meters -------------------- */
export function Meter({
  name, value, max = 1, tone = "blue", right,
}: { name: string; value: number; max?: number; tone?: Tone; right?: ReactNode }) {
  const w = Math.max(0, Math.min(100, (value / (max || 1)) * 100));
  return (
    <div className="meter">
      <div className="top">
        <span className="name">{name}</span>
        <span className="val">{right ?? value.toFixed(4)}</span>
      </div>
      <div className="bar"><div style={{ width: `${w}%`, background: `var(--${tone})` }} /></div>
    </div>
  );
}

/**
 * A stacked contribution bar. Used for the fusion channels so "which channel decided this row"
 * is VISIBLE rather than described — the fusion defect we found was invisible precisely because
 * nobody could see the per-channel split.
 */
export function Stack({ parts }: { parts: Array<{ name: string; value: number; tone: Tone }> }) {
  const total = parts.reduce((a, p) => a + Math.max(0, p.value), 0) || 1;
  return (
    <div>
      <div className="stack">
        {parts.map((p) => (
          <span key={p.name}
                title={`${p.name} — ${(100 * p.value / total).toFixed(1)}%`}
                style={{ flexGrow: Math.max(0, p.value), background: `var(--${p.tone})` }} />
        ))}
      </div>
      <div className="legend">
        {parts.map((p) => (
          <span key={p.name}>
            <i style={{ background: `var(--${p.tone})` }} />
            {p.name} <span className="mono">{(100 * p.value / total).toFixed(0)}%</span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- grammar chips ------------- */
/** Renders a composition as a typed sentence. A string is data; chips are a structure. */
export function Morphemes({ choice, order }: { choice: Record<string, string>; order: string[] }) {
  return (
    <div className="chips">
      {order.map((slot, i) => (
        <span key={slot} className="row" style={{ gap: 7 }}>
          <span className={`chip ${slot.toLowerCase()}`}>
            <span className="slot">{slot}</span>
            <span className="val">{choice[slot] || "—"}</span>
          </span>
          {i < order.length - 1 && <span className="chip sep">/</span>}
        </span>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- pipeline ------------------ */
export function Pipeline({
  stages, active,
}: { stages: Array<{ t: string; d: string; tone: Tone | "grey" }>; active?: number }) {
  return (
    <div className="pipe">
      {stages.map((s, i) => (
        <div key={s.t} className={`stg ${s.tone} ${active === undefined || i <= active ? "on" : ""}`}>
          <div className="i">{String(i + 1).padStart(2, "0")}</div>
          <div className="t">{s.t}</div>
          <div className="d">{s.d}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------------------------------------------------------------- misc ---------------------- */
export function Panel({
  children, accent, tight, className = "", style,
}: {
  children: ReactNode; accent?: Tone; tight?: boolean; className?: string;
  style?: CSSProperties;
}) {
  const a = accent === "blue" ? "accent" : accent ? `accent-${accent}` : "";
  return <div className={`panel ${a} ${tight ? "tight" : ""} ${className}`} style={style}>{children}</div>;
}

export function Notice({
  children, kind = "",
}: { children: ReactNode; kind?: "" | "honest" | "good" | "bad" }) {
  return <div className={`notice ${kind}`}>{children}</div>;
}

export function Why({ children }: { children: ReactNode }) {
  return <div className="why">{children}</div>;
}

export function Skeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="panel">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skel" style={{ width: `${92 - i * 13}%` }} />
      ))}
    </div>
  );
}
