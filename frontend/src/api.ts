import type { Analysis, Health, Sample } from "./types";

const BASE = "/api";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(BASE + path, init);
  } catch {
    throw new Error("Cannot reach the backend. Is it running?");
  }
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON: keep the status line */
    }
    throw new Error(detail);
  }
  const type = resp.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? resp.json() : resp.text()) as Promise<T>;
}

export function analyze(input: File | string, useLlm: boolean): Promise<Analysis> {
  const form = new FormData();
  if (typeof input === "string") form.append("text", input);
  else form.append("file", input);
  return call<Analysis>(`/analyze?use_llm=${useLlm}`, { method: "POST", body: form });
}

export const getAnalysis = (id: string) => call<Analysis>(`/analyses/${encodeURIComponent(id)}`);
export const getHealth = () => call<Health>("/health");
export const listSamples = () => call<Sample[]>("/samples");
export const getSample = (name: string) => call<string>(`/samples/${encodeURIComponent(name)}`);
