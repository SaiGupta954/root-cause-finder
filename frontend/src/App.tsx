import { useEffect, useMemo, useState } from "react";
import { analyze, getAnalysis, getHealth, getSample, listSamples } from "./api";
import GroupsTable from "./components/GroupsTable";
import RootCauseCard from "./components/RootCauseCard";
import Timeline from "./components/Timeline";
import Upload from "./components/Upload";
import type { Analysis, Health, Sample } from "./types";

function setUrlId(id: string | null) {
  const url = new URL(window.location.href);
  if (id) url.searchParams.set("id", id);
  else url.searchParams.delete("id");
  window.history.replaceState(null, "", url);
}

export default function App() {
  const [health, setHealth] = useState<Health | null | "checking">("checking");
  const [samples, setSamples] = useState<Sample[]>([]);
  const [useLlm, setUseLlm] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Analysis | null>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
    listSamples().then(setSamples).catch(() => setSamples([]));
    const id = new URLSearchParams(window.location.search).get("id");
    if (id) {
      setBusy("Loading saved analysis…");
      getAnalysis(id).then(setResult).catch((e: Error) => setError(e.message)).finally(() => setBusy(null));
    }
  }, []);

  async function run(input: File | string, name: string) {
    setError(null);
    setResult(null);
    setBusy(useLlm ? `Analyzing ${name}… the LLM step usually takes under a minute.` : `Analyzing ${name}…`);
    try {
      const r = await analyze(input, useLlm);
      setResult(r);
      setUrlId(r.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function runSample(s: Sample) {
    try {
      const text = await getSample(s.name);
      await run(new File([text], s.name, { type: "text/plain" }), s.title);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const evidence = useMemo(() => new Set(result?.root_cause.evidence_lines.map((e) => e.line) ?? []), [result]);
  const hp = health === "checking" ? null : health;
  const llmOk = hp?.llm.reachable && hp.llm.model_pulled;
  const badge = health === "checking"
    ? { cls: "", icon: "…", text: "Checking backend" }
    : !hp ? { cls: "status-critical", icon: "✕", text: "Backend offline" }
    : llmOk ? { cls: "status-good", icon: "●", text: `LLM ready (${hp.llm.model})` }
    : { cls: "status-warning", icon: "▲", text: `LLM not ready (${hp.llm.model})` };

  return (
    <div className="page">
      <header className="top">
        <div>
          <h1>Root Cause Finder</h1>
          <p className="muted">Upload a Linux log. Get the most likely root cause, with the exact log lines as proof.</p>
        </div>
        <span className={`status ${badge.cls}`} title={hp ? `${hp.llm.model} at ${hp.llm.host}` : ""}>
          <span aria-hidden="true">{badge.icon}</span>
          {badge.text}
        </span>
      </header>

      <Upload busy={!!busy} maxMb={hp?.max_upload_mb ?? 20} samples={samples} useLlm={useLlm} onUseLlm={setUseLlm}
              onFile={(f) => run(f, f.name)} onText={(t, n) => run(t, n)} onSample={runSample} onError={setError} />

      {busy && <div className="notice" role="status"><span className="spinner" aria-hidden="true" />{busy}</div>}
      {error && <div className="notice notice-error" role="alert"><strong>Couldn't analyze the log.</strong> {error}</div>}

      {result && (
        <main className="results">
          <div className="summary small muted">
            <strong>{result.filename}</strong> · {result.stats.lines.toLocaleString()} lines ·{" "}
            {result.stats.patterns} patterns · {result.stats.flagged} flagged · {result.stats.seconds}s
            {result.stats.llm_seconds !== undefined && ` (${result.stats.llm_seconds}s in the LLM)`}
          </div>
          <RootCauseCard analysis={result} />
          <section className="card">
            <h2 className="section-title">Errors over time</h2>
            <Timeline points={result.timeline} />
          </section>
          <section className="card">
            <h2 className="section-title">Top suspicious groups</h2>
            <p className="small muted">Click a row for the reasons, an example line and its line numbers.</p>
            <GroupsTable groups={result.top_groups} evidence={evidence} />
          </section>
        </main>
      )}

      <footer className="small muted">
        Logs never leave this machine when you use a local model. Sample datasets: <a href="https://github.com/logpai/loghub">Loghub</a>.
      </footer>
    </div>
  );
}
