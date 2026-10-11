import type { Analysis } from "./types";

/** Plain-text report for the "Copy report" button: easy to paste into a ticket or chat. */
export function reportText(a: Analysis): string {
  const rc = a.root_cause;
  const out = [
    `Root Cause Finder report: ${a.filename} (${a.stats.lines} lines, analysis ${a.id})`,
    "",
    `Root cause: ${rc.root_cause}`,
    `Category: ${rc.category}` + (rc.alternatives.length ? ` (alternatives: ${rc.alternatives.join(", ")})` : ""),
    `Confidence: ${Math.round(rc.confidence * 100)}%` + (rc.status === "verified" ? ", evidence checked against the file" : ""),
  ];
  if (rc.evidence_lines.length) {
    out.push("", "Evidence:");
    for (const ev of rc.evidence_lines) out.push(`  L${ev.line}: ${ev.text.trim()}`);
  }
  if (rc.next_steps.length) {
    out.push("", "Next steps:");
    for (const step of rc.next_steps) out.push(`  - ${step}`);
  }
  if (rc.status === "not_sure" && rc.error) out.push("", `Note: ${rc.error}`);
  return out.join("\n");
}
