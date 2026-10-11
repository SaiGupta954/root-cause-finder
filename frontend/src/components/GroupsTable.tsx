import { Fragment, useState } from "react";
import type { Group } from "../types";

const FLAG_LABEL: Record<string, string> = {
  error_words: "error words",
  new_pattern: "new",
  spike: "spike",
};

/** Show Drain placeholders like <IP> and <*> as small tags so the fixed text stands out. */
export function Template({ text }: { text: string }) {
  const parts = text.split(/(<[A-Z*]+>)/g);
  return (
    <code className="template">
      {parts.map((p, i) => (/^<[A-Z*]+>$/.test(p) ? <span key={i} className="ph">{p}</span> : p))}
    </code>
  );
}

function when(iso: string | null): string {
  if (!iso) return "–";
  const d = new Date(iso);
  return `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${d.toLocaleTimeString([], { hour12: false })}`;
}

export default function GroupsTable({ groups, evidence }: { groups: Group[]; evidence: Set<number> }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!groups.length) return <p className="muted">Nothing in this log was flagged as suspicious.</p>;
  return (
    <div className="table-wrap">
      <table className="groups">
        <thead>
          <tr>
            <th className="num">#</th>
            <th>Pattern</th>
            <th className="num">Count</th>
            <th>First seen</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((g, i) => {
            const cited = g.line_numbers.some((n) => evidence.has(n));
            const isOpen = open === g.pattern_id;
            return (
              <Fragment key={g.pattern_id}>
                <tr className={`group-row${cited ? " cited" : ""}`} tabIndex={0} aria-expanded={isOpen}
                    onClick={() => setOpen(isOpen ? null : g.pattern_id)}
                    onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), setOpen(isOpen ? null : g.pattern_id))}>
                  <td className="num">{i + 1}</td>
                  <td>
                    <Template text={g.template} />
                    {cited && <span className="cited-tag">cited as evidence</span>}
                  </td>
                  <td className="num">{g.count.toLocaleString()}</td>
                  <td className="nowrap">{when(g.first_seen)}</td>
                  <td>
                    <div className="chips">
                      {g.flags.map((f) => <span key={f} className={`chip flag-${f}`}>{FLAG_LABEL[f] ?? f}</span>)}
                    </div>
                  </td>
                </tr>
                {isOpen && (
                  <tr className="group-detail">
                    <td />
                    <td colSpan={4}>
                      <ul className="reasons">{g.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
                      <div className="small muted">Example</div>
                      <pre className="example">{g.example}</pre>
                      <div className="small muted">
                        Lines: {g.line_numbers.slice(0, 30).join(", ")}
                        {g.count > 30 ? ` … (${g.count} in total)` : ""}
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
