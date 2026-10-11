import { useRef, useState } from "react";
import type { Sample } from "../types";

interface Props {
  busy: boolean;
  maxMb: number;
  samples: Sample[];
  useLlm: boolean;
  onUseLlm: (v: boolean) => void;
  onFile: (f: File) => void;
  onText: (t: string, name: string) => void;
  onSample: (s: Sample) => void;
  onError: (msg: string) => void;
}

export default function Upload({ busy, maxMb, samples, useLlm, onUseLlm, onFile, onText, onSample, onError }: Props) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [paste, setPaste] = useState(false);
  const [text, setText] = useState("");

  function take(f: File | undefined) {
    if (!f) return;
    if (f.size === 0) return onError("The file is empty. Upload a log file with at least one line.");
    if (f.size > maxMb * 1024 * 1024) return onError(`The file is larger than ${maxMb} MB. Upload only the part of the log around the failure.`);
    onFile(f);
  }

  return (
    <section className="card upload" aria-label="Upload a log">
      {paste ? (
        <div className="paste">
          <label htmlFor="paste-box" className="small muted">Paste log lines</label>
          <textarea id="paste-box" value={text} onChange={(e) => setText(e.target.value)} spellCheck={false}
                    placeholder="Oct 11 09:20:03 web01 postgres[4410]: ERROR: could not extend file ..." rows={8} />
          <div className="row">
            <button className="btn" disabled={busy || !text.trim()} onClick={() => onText(text, "pasted.log")}>Analyze</button>
            <button className="btn btn-ghost" onClick={() => setPaste(false)}>Upload a file instead</button>
          </div>
        </div>
      ) : (
        <div
          className={`drop${drag ? " drag" : ""}${busy ? " busy" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busy) take(e.dataTransfer.files[0]); }}
        >
          <p className="drop-title">Drop a Linux log file here</p>
          <p className="muted small">syslog, auth.log, journalctl or docker logs output · up to {maxMb} MB</p>
          <div className="row center">
            <button className="btn" disabled={busy} onClick={() => input.current?.click()}>Choose file</button>
            <button className="btn btn-ghost" disabled={busy} onClick={() => setPaste(true)}>Paste lines</button>
          </div>
          <input ref={input} type="file" hidden onChange={(e) => { take(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
      )}

      <div className="upload-foot">
        {samples.length > 0 && (
          <div className="samples">
            <span className="small muted">Try a sample from the failure lab:</span>
            {samples.map((s) => (
              <button key={s.name} className="chip chip-button" disabled={busy} onClick={() => onSample(s)}>{s.title}</button>
            ))}
          </div>
        )}
        <label className="toggle small">
          <input type="checkbox" checked={useLlm} onChange={(e) => onUseLlm(e.target.checked)} disabled={busy} />
          Ask the LLM for the root cause (off = only parse and flag, takes a second)
        </label>
      </div>
    </section>
  );
}
