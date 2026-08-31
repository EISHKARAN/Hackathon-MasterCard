/* ARCHIVE — grammar space and quality-diversity coverage. */
import { report, num, pct } from "@/lib/reports";
import { Kicker, Kpi, Notice, Tech, Why } from "@/components/ui";
// Rendered at BUILD time. The records are committed artefacts of a finished run, not live data,
// so a snapshot is correct here and lets the whole prototype ship as one service.
export const dynamic = "force-static";

export default function Archive() {
  const g: any = report("grammar_census.json");
  const a: any = report("archive_report.json");
  if (!g && !a) return <Notice kind="bad">The grammar and archive reports have not been generated yet.</Notice>;
  const cov = a?.coverage ?? {};
  const slots: Record<string, number> = g?.slot_counts ?? {};

  return (
    <div>
      <Kicker tone="red">Criterion 1 · diversity of attacks</Kicker>
      <h1>A grammar, not a list</h1>
      <p className="sub">
        Attacks are compositions in a six-slot typed grammar. A compatibility matrix rejects the
        combinations that are physically impossible on a rail, so what remains is the space of attacks
        that could actually happen.
      </p>

      <div className="grid g3">
        <Kpi label="raw combinations" value={num(g?.raw_space)} tone="blue" denom="every slot crossed" />
        <Kpi label="type-legal compositions" value={num(g?.type_legal)} tone="red"
             denom={`pruning rate ${pct(g?.pruning_rate)}`} />
        <Kpi label="archive cells reached"
             value={`${num(cov.occupied_cells ?? g?.reachable_cells)} / ${num(g?.feasible_cells)}`}
             tone="green" denom={`coverage ceiling ${pct(g?.coverage_ceiling)}`} />
      </div>

      {Object.keys(slots).length > 0 && (
        <>
          <h2>The six slots</h2>
          <div className="tbl-wrap">
            <table><thead><tr><th>slot</th><th className="num">morphemes</th></tr></thead>
              <tbody>{Object.entries(slots).map(([k, v]) => (
                <tr key={k}><td className="mono">{k}</td><td className="num">{num(v)}</td></tr>))}</tbody>
            </table>
          </div>
        </>
      )}

      <Why>
        The rejected strings are not an omission. A beneficiary leg on an assisted cash-out rail is
        impossible because that rail terminates in physical cash, so the grammar refuses it rather than
        generating an event no real system could emit.
      </Why>

      <Tech items={[
        ["nominal cells", <span className="mono" key="a">{num(g?.nominal_cells)}</span>],
        ["feasible cells", <span className="mono" key="b">{num(g?.feasible_cells)}</span>],
        ["reachable cells", <span className="mono" key="c">{num(g?.reachable_cells)}</span>],
      ]} />
      {a?.note && <Notice kind="honest">{a.note}</Notice>}
    </div>
  );
}
