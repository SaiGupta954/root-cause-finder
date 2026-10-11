import { useState } from "react";
import { reportText } from "../report";
import { CATEGORY_LABEL, type Analysis } from "../types";

const ERROR_WORDS =
  /(no space left on device|address already in use|permission denied|out of memory|cannot allocate memory|temporary failure in name resolution|could not resolve[^:]*|failed password|invalid user|syntax error|unknown directive|killed process|\berror\b|\bfailed\b|\bfailure\b|\bdenied\b|\brefused\b|\btimed out\b|\bfatal\b|\bkilled\b)/gi;

/** Highlight the words that make a line look like an error. */
function Highlight({ text }: { text: string }) {
  const parts = text.split(ERROR_WORDS);
  return <>{parts.map((p, i) => (i % 2 === 1 ? <mark key={i}>{p}</mark> : p))}</>;
}

/** Turn `backticks` in next steps into code. */
function Step({ text }: { text: string }) {
  return <>{text.split(/(`[^`]+`)/g).map((p, i) => (p.startsWith("`") && p.endsWith("`") && p.length > 1
    ? <code key={i}>{p.slice(1, -1)}</code> : p))}</>;
}

const title = (id: string) => CATEGORY_LABEL[id] ?? id.replace(/_/g, " ");

export default function RootCauseCard({ analysis }: { analysis: Analysis }) {
  const rc = analysis.root_cause;
  const [copied, setCopied] = useState<"idle" | "ok" | "fail">("idle");
  const sure = rc.status === "verified";
  const pct = Math.round(rc.confidence * 100);

  async function copy() {
    try {
      await navigator.clipboard.writeText(reportText(analysis));
      setCopied("ok");
    } catch {
      setCopied("fail");
    }
    setTimeout(() => setCopied("idle"), 2000);
  }

  return (
    <section className={`card root-cause ${sure ? "is-verified" : "is-unsure"}`} aria-labelledby="rc-title">
      <div className="rc-head">
        <span className={`status ${sure ? "status-good" : "status-warning"}`}>
          <span aria-hidden="true">{sure ? "✓" : "?"}</span>
          {sure ? "Evidence checked" : "Not sure"}
        </span>
        <button className="btn btn-secondary" onClick={copy}>
          {copied === "ok" ? "Copied" : copied === "fail" ? "Copy failed" : "Copy report"}
        </button>
      </div>

      <h2 id="rc-title" className="rc-title">{sure ? rc.root_cause : "Not sure what the root cause is"}</h2>

      {sure ? (
        <div className="rc-meta">
          <span className="chip chip-strong">{title(rc.category)}</span>
          {rc.alternatives.length > 0 && (
            <span className="small muted">Less likely: {rc.alternatives.map(title).join(", ")}</span>
          )}
          <span className="confidence" title="The model's confidence, reduced for every evidence line that failed the check">
            <span className="meter" aria-hidden="true"><span style={{ width: `${pct}%` }} /></span>
            {pct}% confidence
          </span>
        </div>
      ) : (
        <p className="muted">
          {rc.error ?? "None of the evidence the model gave could be found in the file, so there is no answer to trust."}
          {rc.unverified_guess && <> The model's unchecked guess was: <em>{rc.unverified_guess}</em></>}
        </p>
      )}

      {rc.evidence_lines.length > 0 && (
        <>
          <h3>Evidence from the log</h3>
          <ol className="evidence">
            {rc.evidence_lines.map((ev) => (
              <li key={ev.line}>
                <span className="ln">L{ev.line}</span>
                <code><Highlight text={ev.text} /></code>
              </li>
            ))}
          </ol>
        </>
      )}
      {rc.dropped_evidence.length > 0 && (
        <p className="small muted">
          {rc.dropped_evidence.length} evidence line{rc.dropped_evidence.length > 1 ? "s" : ""} from the model failed the
          check and {rc.dropped_evidence.length > 1 ? "were" : "was"} dropped ({rc.dropped_evidence.map((d) => d.reason).join("; ")}).
        </p>
      )}

      {rc.next_steps.length > 0 && (
        <>
          <h3>Next steps{rc.next_steps_source ? ` · from the “${title(rc.next_steps_source)}” card` : ""}</h3>
          <ul className="steps">{rc.next_steps.map((s) => <li key={s}><Step text={s} /></li>)}</ul>
        </>
      )}

      {analysis.similar_cards.length > 0 && (
        <div className="kb">
          <h3>Closest known failures</h3>
          <ul className="kb-list">
            {analysis.similar_cards.map((c) => (
              <li key={c.id}>
                <strong>{c.title}</strong>
                <span className="muted small"> · similarity {c.similarity.toFixed(2)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
