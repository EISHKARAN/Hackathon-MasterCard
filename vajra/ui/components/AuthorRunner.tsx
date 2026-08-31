"use client";
/* The only interactive island in the app. Isolated on purpose: if the backend is unreachable this
 * component degrades to a message, and the server-rendered walkthrough around it still stands. */
import { useEffect, useState } from "react";
import { getJSON, postJSON } from "@/lib/api";
import { Badge, Kpi, Morphemes, Notice, Panel, Step, Tech, Why } from "@/components/ui";

const SLOTS = ["ACCESS", "TRUST", "RAIL", "EVASION", "MONETISATION", "LABEL"];
const f4 = (v: any) => (typeof v === "number" && isFinite(v) ? v.toFixed(4) : "—");

export function AuthorRunner() {
  const [picker, setPicker] = useState<any>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [legal, setLegal] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    getJSON("/picker").then((p: any) => {
      setPicker(p);
      const init: Record<string, string> = {};
      for (const s of p.slots) init[s.slot] = s.values[0].id;
      setChoice(init);
    }).catch((e) => setErr(String(e)));
  }, []);

  useEffect(() => {
    if (!picker) return;
    (async () => {
      const next: Record<string, string[]> = {};
      for (const s of SLOTS) next[s] = (await postJSON("/legal-next", { partial: choice, slot: s })).legal;
      setLegal(next);
    })().catch(() => {});
  }, [choice, picker]);

  const grammar = SLOTS.map((s) => `${s}=${choice[s] || ""}`).join("/");

  async function run() {
    setBusy(true); setResult(null); setErr("");
    try { setResult(await postJSON("/author-attack", { grammar_str: grammar, view: "issuer" })); }
    catch (e) { setErr(String(e)); }
    setBusy(false);
  }

  if (err && !picker)
    return <Notice kind="bad">
      The composer service is not reachable, so live authoring is unavailable. The walkthrough above
      is unaffected — it is rendered from the committed run.
    </Notice>;

  if (!picker)
    return <Panel><div className="skel" style={{ width: "40%" }} /><div className="skel" /><div className="skel" style={{ width: "70%" }} /></Panel>;

  const out = result?.outcome;
  return (
    <div>
      <Panel accent="red">
        <div className="spread" style={{ marginBottom: 14 }}>
          <span className="label">Compose a composition</span>
          <span className="badge info">picker pruned to type-legal</span>
        </div>
        {picker.slots.map((s: any) => {
          const allowed = legal[s.slot];
          const tone = s.slot === "ACCESS" ? "var(--red)" : s.slot === "EVASION" ? "var(--amber)"
            : s.slot === "RAIL" ? "var(--blue)" : s.slot === "MONETISATION" ? "var(--purple)" : undefined;
          return (
            <div key={s.slot} className="row" style={{ marginBottom: 9 }}>
              <span className="label" style={{ width: 118, flex: "0 0 118px" }}>{s.slot}</span>
              <select value={choice[s.slot] || ""} style={{ minWidth: 320, borderColor: tone }}
                      onChange={(e) => setChoice({ ...choice, [s.slot]: e.target.value })}>
                {s.values.map((v: any) => {
                  const ok = !allowed || allowed.includes(v.id);
                  return <option key={v.id} value={v.id} disabled={!ok}>
                    {v.label}{ok ? "" : " — would not type-check"}</option>;
                })}
              </select>
              <span className="mono" style={{ color: "var(--faint)", fontSize: 11 }}>
                {allowed ? `${allowed.length}/${s.values.length}` : `${s.values.length}/${s.values.length}`} legal
              </span>
            </div>
          );
        })}
        <div style={{ margin: "16px 0 6px" }}><span className="label">the composition, as a typed sentence</span></div>
        <Morphemes choice={choice} order={SLOTS} />
        <div className="row" style={{ marginTop: 14 }}>
          <button onClick={run} disabled={busy} className={busy ? "" : "go"}>
            {busy ? "compiling · executing · scoring…" : "Run it against the gate"}
          </button>
          <span className="mono" style={{ color: "var(--faint)", fontSize: 11 }}>
            scored against the promoted model, not one retrained for this demo
          </span>
        </div>
      </Panel>

      {err && <Notice kind="bad">{err}</Notice>}

      {result && (
        <div style={{ marginTop: 8 }}>
          <Step n={1} title="Did it compile?" tone={result.compiled?.ok ? "green" : "red"} />
          {result.compiled?.ok
            ? <Panel tight><div className="row">
                <Badge kind="pass">type-legal</Badge>
                <span className="sub" style={{ margin: 0 }}>
                  occupies archive cell <span className="mono">{result.compiled.cell_id}</span> · resolves{" "}
                  <b>{result.compiled.signatures?.length ?? 0}</b> observable signatures to schema fields.
                </span></div></Panel>
            : <Notice kind="bad"><Badge kind="fail">rejected</Badge>{" "}
                {result.compiled?.reasons?.join("; ")} — a rejection is an explanation, naming the
                pairwise constraint the composition violates.</Notice>}

          {result.stage === "scored" && out && (
            <>
              <Step n={2} title="How the attack happened" tone="green" />
              <div className="grid g4">
                <Kpi label="events generated" value={result.n_events_generated} tone="green"
                     denom="structurally legal messages, not rows" />
                <Kpi label="invariant gate" value={result.f1?.violations ?? 0}
                     tone={result.f1?.passed ? "green" : "red"}
                     denom={result.f1?.passed ? "violations — gate passed" : "violations — gate FAILED"} />
                <Kpi label="signatures resolved" value={result.compiled?.signatures?.length ?? 0} tone="blue"
                     denom="observables mapped to schema fields" />
                <Kpi label="end to end" value={`${Math.round(result.elapsed_ms ?? 0)} ms`} tone="blue"
                     denom={result.elapsed_note} />
              </div>

              <Step n={3} title="How we identified it" tone="blue" />
              <Tech items={[["scored by", <span className="mono" key="a">{result.model_version}</span>],
                            ["endpoint", "promoted · pinned"], ["truth", "oracle attack labels"]]} />
              <div className="grid g2">
                <Panel accent="blue">
                  <div className="spread" style={{ marginBottom: 10 }}>
                    <span className="label">Outcome split</span>
                    {out.buckets_sum_to_total
                      ? <Badge kind="pass">rows sum to total</Badge>
                      : <Badge kind="fail">does not sum</Badge>}
                  </div>
                  <div className="tbl-wrap"><table><tbody>
                    <tr><td>caught by score</td><td className="num" style={{ color: "var(--green)", fontWeight: 700 }}>{out.caught_by_score}</td></tr>
                    <tr><td>routed to abstention</td><td className="num" style={{ color: "var(--purple)", fontWeight: 700 }}>{out.routed_to_abstention}</td></tr>
                    <tr><td>blocked by invariant guard</td><td className="num" style={{ color: "var(--blue)", fontWeight: 700 }}>{out.blocked_by_invariant}</td></tr>
                    <tr><td>slipped through</td><td className="num" style={{ color: "var(--red)", fontWeight: 700 }}>{out.approved_slipped_through}</td></tr>
                    <tr><td><b>total</b></td><td className="num"><b>{out.total_events}</b></td></tr>
                  </tbody></table></div>
                  <Why>{out.note}</Why>
                </Panel>
                <Panel accent="blue">
                  <div className="spread" style={{ marginBottom: 10 }}>
                    <span className="label">Per-event score trace</span>
                    <span className="badge info">real calls · real latency</span>
                  </div>
                  <div className="tbl-wrap"><table>
                    <thead><tr><th className="num">score</th><th>band</th><th className="num">conformal p</th><th>why</th></tr></thead>
                    <tbody>{(result.score_trace_sample ?? []).map((t: any, i: number) => (
                      <tr key={i}><td className="num">{f4(t.score)}</td>
                        <td><span className={`pill ${t.band}`}>{String(t.band).replace(/_/g, " ")}</span></td>
                        <td className="num">{f4(t.conformal_p)}</td>
                        <td style={{ fontSize: 11, color: "var(--muted)" }}>
                          {(t.reason_texts ?? []).slice(0, 2).join("; ") || "—"}</td></tr>))}</tbody>
                  </table></div>
                  <Why>
                    The reason column is the code the decision actually carried, from a fixed
                    vocabulary. A score without an explanation is not an action an issuer can take.
                  </Why>
                </Panel>
              </div>
              {result.bound_statement && <Notice kind="honest">{result.bound_statement}</Notice>}
            </>
          )}
        </div>
      )}
    </div>
  );
}
