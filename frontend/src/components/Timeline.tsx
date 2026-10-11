import { Area, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { TimelinePoint } from "../types";

const MAX_POINTS = 240;

interface Point extends TimelinePoint {
  label: string;
}

function fmt(iso: string, withDay: boolean): string {
  const d = new Date(iso);
  const hm = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  return withDay ? `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${hm}` : hm;
}

/** Long logs: merge neighbouring minutes so the chart stays readable. */
function bucket(points: TimelinePoint[]): { data: Point[]; perBucket: number } {
  const days = new Set(points.map((p) => p.minute.slice(0, 10)));
  const withDay = days.size > 1;
  const perBucket = Math.max(1, Math.ceil(points.length / MAX_POINTS));
  const data: Point[] = [];
  for (let i = 0; i < points.length; i += perBucket) {
    const chunk = points.slice(i, i + perBucket);
    data.push({
      minute: chunk[0].minute,
      label: fmt(chunk[0].minute, withDay),
      lines: chunk.reduce((s, p) => s + p.lines, 0),
      errors: chunk.reduce((s, p) => s + p.errors, 0),
    });
  }
  return { data, perBucket };
}

function ChartTooltip({ active, payload }: { active?: boolean; payload?: { payload: Point }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="chart-tip">
      <div className="chart-tip-title">{p.label}</div>
      <div className="chart-tip-row">
        <span className="key key-errors" />
        <strong>{p.errors}</strong> errors
      </div>
      <div className="chart-tip-row">
        <span className="key key-lines" />
        <strong>{p.lines}</strong> lines
      </div>
    </div>
  );
}

export default function Timeline({ points }: { points: TimelinePoint[] }) {
  if (!points.length) {
    return <p className="muted">No timestamps found, so there is no timeline for this log.</p>;
  }
  const { data, perBucket } = bucket(points);
  const totalErrors = points.reduce((s, p) => s + p.errors, 0);
  return (
    <figure className="timeline">
      <div className="legend" aria-hidden="true">
        <span><span className="key key-errors" /> Error lines</span>
        <span><span className="key key-lines" /> All lines</span>
      </div>
      <div className="chart-box" role="img"
           aria-label={`Timeline: ${totalErrors} error lines across ${points.length} active minutes`}>
        <ResponsiveContainer width="100%" height={220}>
          <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke="var(--grid)" />
            <XAxis dataKey="label" tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false}
                   axisLine={{ stroke: "var(--axis)" }} minTickGap={40} />
            <YAxis allowDecimals={false} tick={{ fill: "var(--muted)", fontSize: 11 }} tickLine={false}
                   axisLine={false} width={48} />
            <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--axis)", strokeWidth: 1 }} />
            <Area type="monotone" dataKey="lines" stroke="var(--series-1)" strokeWidth={1.5}
                  fill="var(--series-1)" fillOpacity={0.12} isAnimationActive={false} />
            <Line type="monotone" dataKey="errors" stroke="var(--series-2)" strokeWidth={2} dot={false}
                  activeDot={{ r: 4, stroke: "var(--surface)", strokeWidth: 2 }} isAnimationActive={false} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      <figcaption className="muted small">
        Lines per {perBucket === 1 ? "minute" : `${perBucket} active minutes`}. Minutes with no log lines are
        skipped, so long quiet gaps don't flatten the chart.
      </figcaption>
    </figure>
  );
}
