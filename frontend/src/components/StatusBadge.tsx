import type { BotStatus } from "../api/types";

/**
 * Accounts whose trading-mode badge is suppressed in the user and public views.
 *
 * Presentation only — it changes nothing about how the bot trades. ``BotInstance.dry_run``
 * still decides that, and the admin panel deliberately keeps showing the real mode so an
 * admin is never misled about which bots are on real money.
 */
const MODE_BADGE_HIDDEN = new Set(["alfred"]);

/** Bot containers are named ``cp-bot-<username>`` (see ``provisioning._container_name``). */
export function accountOfContainer(containerName: string): string {
  return containerName.replace(/^cp-bot-/, "");
}

export function StatusBadge({ status }: { status: BotStatus }) {
  return <span className={`badge ${status}`}>{status}</span>;
}

/**
 * Trading-mode badge. Pass ``account`` in views where the badge may be suppressed;
 * omit it (as the admin panel does) to always render the real mode.
 */
export function ModeBadge({ dryRun, account }: { dryRun: boolean; account?: string }) {
  if (account !== undefined && MODE_BADGE_HIDDEN.has(account)) return null;
  return <span className={`badge ${dryRun ? "dry" : "live"}`}>{dryRun ? "dry-run" : "LIVE"}</span>;
}
