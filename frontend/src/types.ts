export interface EvidenceLine {
  line: number;
  text: string;
}

export interface RootCause {
  status: "verified" | "not_sure";
  root_cause: string;
  category: string;
  alternatives: string[];
  confidence: number;
  evidence_lines: EvidenceLine[];
  dropped_evidence: { item: unknown; reason: string }[];
  next_steps: string[];
  error?: string;
  unverified_guess?: string;
}

export interface Group {
  pattern_id: number;
  template: string;
  count: number;
  first_seen: string | null;
  last_seen: string | null;
  flags: string[];
  reasons: string[];
  score: number;
  line_numbers: number[];
  example: string;
}

export interface TimelinePoint {
  minute: string;
  lines: number;
  errors: number;
}

export interface Analysis {
  id: string;
  created_at: string;
  filename: string;
  stats: {
    lines: number;
    patterns: number;
    flagged: number;
    start: string | null;
    end: string | null;
    seconds: number;
    llm_seconds?: number;
  };
  timeline: TimelinePoint[];
  top_groups: Group[];
  keyword_baseline: { category: string; count: number; lines: number[] }[];
  similar_cards: { id: string; title: string; similarity: number; fix: string }[];
  root_cause: RootCause;
}

export interface Sample {
  name: string;
  title: string;
  bytes: number;
}

export interface Health {
  status: string;
  max_upload_mb: number;
  llm: { host: string; model: string; reachable: boolean; model_pulled: boolean };
}

export const CATEGORY_LABEL: Record<string, string> = {
  disk_full: "Disk full",
  dns_failure: "DNS failure",
  crash_loop: "Crash loop",
  permission_denied: "Permission denied",
  port_in_use: "Port in use",
  out_of_memory: "Out of memory",
  bad_config: "Bad config",
  ssh_bruteforce: "SSH brute force",
  other: "Other",
};
