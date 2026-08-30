"use client";
/* ============================================================================================
   ArchScene — the architecture as an isometric SVG, split into its three pillars, lit in order.

   WHY SVG AND NOT THREE.JS. The WebGL version was rewritten four times and never framed correctly:
   the canvas element's layout size and its drawing buffer kept disagreeing, so on a retina display
   the element laid out at 2x, the container clipped it to the top-left quadrant, and the scene's
   centre landed at the panel's bottom-right corner. An SVG `viewBox` scales to its container BY
   DEFINITION, so that entire class of bug cannot occur. Three further wins that matter for a demo:
     *  text is real <text>, so a label can never be clipped by a fixed-size sprite canvas;
     *  it renders identically on a machine with no WebGL, which a locked-down venue laptop may be;
     *  it costs no dependency, where three.js was a 339 kB chunk.

   The geometry is a hand-rolled axonometric projection, and its numbers were solved rather than
   guessed: at U = 108 px per world unit the content fills 98% of the viewBox horizontally and 84%
   vertically, verified arithmetically before this file was written.

   WHAT IT SHOWS. Three zone slabs matching figures/architecture-dark.png — red ARENA, green
   vajra-sim, blue GATE. Assembled while idle (the diagram); they split apart and light one at a
   time as a run progresses: AUTHOR, then SIMULATE, then DEFEND.

   IT IS AN INSTRUMENT, NOT DECORATION. Packet count follows the real generated-event count, and the
   four outcome lanes are scaled to the REAL outcome split, so if the model misses, the red lane is
   visibly tall.
   ============================================================================================ */
import { useMemo } from "react";

export type Phase = "idle" | "author" | "simulate" | "defend";

export type Outcome = {
  caught_by_score?: number;
  routed_to_abstention?: number;
  blocked_by_invariant?: number;
  approved_slipped_through?: number;
};

const RED = "#e8505b", GREEN = "#3dd68c", BLUE = "#4a9eff", PURPLE = "#a97bf0";
const MUTED = "#9a9aa8", FAINT = "#6a6b78";

/* Solved layout constants — see the header. */
const U = 108, CX = 620, CY = 235, VB_W = 1240, VB_H = 300;
const W = 2.8, D = 2.9, T = 0.26;              // slab width / depth / thickness, world units

const PHASE_IDX: Record<Phase, number> = { idle: -1, author: 0, simulate: 1, defend: 2 };

const ZONES = [
  { name: "AUTHOR", sub: "ARENA · grammar", colour: RED, x: -3.6 },
  { name: "SIMULATE", sub: "vajra-sim · rails", colour: GREEN, x: 0 },
  { name: "DEFEND", sub: "GATE · three bands", colour: BLUE, x: 3.6 },
];

const LANES = [
  { key: "caught_by_score", label: "caught", colour: GREEN, dx: -0.95 },
  { key: "routed_to_abstention", label: "abstain", colour: PURPLE, dx: -0.32 },
  { key: "blocked_by_invariant", label: "G0", colour: BLUE, dx: 0.32 },
  { key: "approved_slipped_through", label: "slipped", colour: RED, dx: 0.95 },
] as const;

/** Axonometric projection: +x right, +y up, +z away (up-and-right). */
const P = (x: number, y: number, z: number): [number, number] =>
  [CX + x * U + z * 0.45 * U, CY - y * U - z * 0.26 * U];

const poly = (pts: Array<[number, number]>) => pts.map(([a, b]) => `${a.toFixed(1)},${b.toFixed(1)}`).join(" ");

/** One slab: top face plus two side faces, so it reads as a solid plate. */
function Slab({ x, colour, lit }: { x: number; colour: string; lit: number }) {
  const top = poly([P(x - W / 2, T, -D / 2), P(x + W / 2, T, -D / 2), P(x + W / 2, T, D / 2), P(x - W / 2, T, D / 2)]);
  const front = poly([P(x - W / 2, 0, -D / 2), P(x + W / 2, 0, -D / 2), P(x + W / 2, T, -D / 2), P(x - W / 2, T, -D / 2)]);
  const right = poly([P(x + W / 2, 0, -D / 2), P(x + W / 2, 0, D / 2), P(x + W / 2, T, D / 2), P(x + W / 2, T, -D / 2)]);
  return (
    <g>
      <polygon points={front} fill="#101219" stroke={colour} strokeOpacity={0.35 + lit * 0.5} strokeWidth={1} />
      <polygon points={right} fill="#0c0e14" stroke={colour} strokeOpacity={0.35 + lit * 0.5} strokeWidth={1} />
      <polygon points={top} fill={colour} fillOpacity={0.10 + lit * 0.20}
               stroke={colour} strokeOpacity={0.45 + lit * 0.55} strokeWidth={1.4} />
    </g>
  );
}

export function ArchScene({
  phase, nEvents = 0, outcome, height = 300,
}: { phase: Phase; nEvents?: number; outcome?: Outcome; height?: number }) {
  const idx = PHASE_IDX[phase];
  const spread = idx < 0 ? 0.62 : 1;               // assembled (the diagram) -> split apart

  const total = LANES.reduce((a, l) => a + Math.max(0, (outcome?.[l.key] as number) ?? 0), 0);

  /* Packet count tracks the real event count, capped so a stream reads as a stream. */
  const nPackets = Math.max(0, Math.min(26, Math.round((nEvents || 0) / 3)));
  const packets = useMemo(() => Array.from({ length: nPackets }, (_, i) => {
    // Deterministic spread of lanes by the REAL outcome weights, so the stream's composition IS
    // the result rather than an illustration of it.
    let lane = 0;
    if (total > 0) {
      let acc = ((i + 0.5) / nPackets) * total;
      for (let k = 0; k < LANES.length; k++) {
        acc -= Math.max(0, (outcome?.[LANES[k].key] as number) ?? 0);
        if (acc <= 0) { lane = k; break; }
      }
    }
    return { i, lane, delay: (i / Math.max(1, nPackets)) * 2.4, dur: 2.2 + (i % 5) * 0.18 };
  }), [nPackets, total, outcome]);

  const zx = (i: number) => ZONES[i].x * spread;

  return (
    <div style={{ width: "100%", height, overflow: "hidden", borderRadius: 10, background: "#0f1015" }}>
      <style>{`
        @keyframes vjHop1 { 0%{opacity:0} 8%{opacity:1} 92%{opacity:1} 100%{opacity:0} }
        .vjSlab { transition: transform .55s cubic-bezier(.4,0,.2,1); }
        .vjLane { transition: transform .6s cubic-bezier(.4,0,.2,1), opacity .4s ease; }
        .vjMorph { transition: opacity .4s ease; }
        @media (prefers-reduced-motion: reduce) {
          .vjPkt { animation: none !important; opacity: .9 !important; }
        }
      `}</style>
      <svg viewBox={`0 0 ${VB_W} ${VB_H}`} width="100%" height="100%"
           preserveAspectRatio="xMidYMid meet" style={{ display: "block" }}>
        <defs>
          {ZONES.map((z) => (
            <radialGradient key={z.name} id={`gl${z.name}`} cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor={z.colour} stopOpacity={0.30} />
              <stop offset="100%" stopColor={z.colour} stopOpacity={0} />
            </radialGradient>
          ))}
        </defs>

        {ZONES.map((z, i) => {
          const lit = idx === i ? 1 : idx > i ? 0.45 : 0;
          const [gx, gy] = P(0, 0, 0);
          const [tx] = P(z.x * spread, 0, 0);
          const dxPx = tx - P(z.x, 0, 0)[0];
          const [lx, ly] = P(z.x, 1.30, 0);
          const [sx2, sy2] = P(z.x, 1.02, 0);
          return (
            <g key={z.name} className="vjSlab" style={{ transform: `translateX(${dxPx.toFixed(1)}px)` }}>
              {/* glow under the active zone */}
              <ellipse cx={P(z.x, 0, 0)[0]} cy={P(z.x, 0, 0)[1]} rx={W * U * 0.62} ry={26}
                       fill={`url(#gl${z.name})`} opacity={lit} />
              <Slab x={z.x} colour={z.colour} lit={lit} />

              {/* the six typed morphemes, on the AUTHOR slab */}
              {i === 0 && Array.from({ length: 6 }, (_, k) => {
                const mx = z.x + (k - 2.5) * 0.42;
                const c = poly([P(mx - 0.15, T, -0.2), P(mx + 0.15, T, -0.2), P(mx + 0.15, T, 0.2), P(mx - 0.15, T, 0.2)]);
                const f = poly([P(mx - 0.15, T, -0.2), P(mx + 0.15, T, -0.2), P(mx + 0.15, T + 0.26, -0.2), P(mx - 0.15, T + 0.26, -0.2)]);
                return (
                  <g key={k} className="vjMorph" style={{ opacity: idx >= 0 ? 1 : 0, transitionDelay: `${k * 70}ms` }}>
                    <polygon points={f} fill={RED} fillOpacity={0.5} stroke={RED} strokeWidth={0.8} />
                    <polygon points={c} fill={RED} fillOpacity={0.85} />
                  </g>
                );
              })}

              {/* outcome lanes, on the DEFEND slab */}
              {i === 2 && LANES.map((l) => {
                const share = total > 0 ? Math.max(0, (outcome?.[l.key] as number) ?? 0) / total : 0;
                // 1.35, not 1.7: at 1.7 a lane holding the whole split pushes its % label to screen y=0 and
                // the viewBox clips it. Solved against the 217px of headroom above CY.
                const h = idx >= 2 ? Math.max(0.05, share * 1.35) : 0.001;
                const bx = z.x + l.dx;
                const top = poly([P(bx - 0.17, T + h, -0.17), P(bx + 0.17, T + h, -0.17), P(bx + 0.17, T + h, 0.17), P(bx - 0.17, T + h, 0.17)]);
                const fr = poly([P(bx - 0.17, T, -0.17), P(bx + 0.17, T, -0.17), P(bx + 0.17, T + h, -0.17), P(bx - 0.17, T + h, -0.17)]);
                const ri = poly([P(bx + 0.17, T, -0.17), P(bx + 0.17, T, 0.17), P(bx + 0.17, T + h, 0.17), P(bx + 0.17, T + h, -0.17)]);
                const [px2, py2] = P(bx, T + h + 0.22, 0);
                return (
                  <g key={l.key} className="vjLane" style={{ opacity: idx >= 2 ? 1 : 0 }}>
                    <polygon points={fr} fill={l.colour} fillOpacity={0.55} />
                    <polygon points={ri} fill={l.colour} fillOpacity={0.35} />
                    <polygon points={top} fill={l.colour} fillOpacity={0.95} />
                    {idx >= 2 && share > 0.02 && (
                      <text x={px2} y={py2} fill={l.colour} fontSize={13} textAnchor="middle"
                            fontFamily="ui-monospace, Menlo, monospace" fontWeight={700}>
                        {Math.round(share * 100)}%
                      </text>
                    )}
                  </g>
                );
              })}

              <text x={lx} y={ly} fill={z.colour} fontSize={26} fontWeight={800} textAnchor="middle"
                    fontFamily="ui-monospace, Menlo, monospace" opacity={idx >= i ? 1 : 0.4}>
                {z.name}
              </text>
              <text x={sx2} y={sy2} fill={idx === i ? MUTED : FAINT} fontSize={14} textAnchor="middle"
                    fontFamily="ui-monospace, Menlo, monospace">
                {z.sub}
              </text>
            </g>
          );
        })}

        {/* packets: AUTHOR -> SIMULATE, then SIMULATE -> DEFEND lane, on an arc */}
        {idx >= 1 && packets.map((p) => {
          const twoHop = idx >= 2;
          const a = P(zx(0) + W / 2 * 0.4, T + 0.35, 0);
          const b = P(zx(1), T + 1.05, 0);
          const c = P(zx(twoHop ? 2 : 1) + (twoHop ? LANES[p.lane].dx : 0), T + 0.5, 0);
          const mid = P((zx(1) + zx(2)) / 2, T + 1.15, 0);
          const d = twoHop
            ? `M ${a[0]},${a[1]} Q ${b[0]},${b[1] - 30} ${P(zx(1), T + 0.45, 0)[0]},${P(zx(1), T + 0.45, 0)[1]} Q ${mid[0]},${mid[1] - 30} ${c[0]},${c[1]}`
            : `M ${a[0]},${a[1]} Q ${b[0]},${b[1] - 34} ${c[0]},${c[1]}`;
          const col = twoHop ? LANES[p.lane].colour : GREEN;
          return (
            <g key={p.i}>
              <circle r={4.2} fill={col} className="vjPkt"
                      style={{ animation: `vjHop1 ${p.dur}s linear ${p.delay}s infinite`, opacity: 0 }}>
                <animateMotion dur={`${p.dur}s`} begin={`${p.delay}s`} repeatCount="indefinite" path={d} />
              </circle>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default ArchScene;
