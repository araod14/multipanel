import type { BotStatus } from "../api/types";

export function StatusBadge({ status }: { status: BotStatus }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

export function ModeBadge({ dryRun }: { dryRun: boolean }) {
  return <span className={`badge ${dryRun ? "dry" : "live"}`}>{dryRun ? "dry-run" : "LIVE"}</span>;
}
