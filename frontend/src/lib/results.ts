import type { PublicAccount } from "../api/types";

export type AccountMode = "all" | "live" | "dry";
export type AccountOrder = "name" | "profit" | "roi";

/** Keep the API order intact; missing metrics always follow measured accounts. */
export function filterAccounts(
  accounts: PublicAccount[], search: string, mode: AccountMode, order: AccountOrder,
): PublicAccount[] {
  const term = search.trim().toLocaleLowerCase("es");
  return accounts
    .filter((a) => a.username.toLocaleLowerCase("es").includes(term)
      && (mode === "all" || a.dry_run === (mode === "dry")))
    .sort((a, b) => {
      const byName = a.username.localeCompare(b.username, "es");
      if (order === "name") return byName;
      const key = order === "profit" ? "profit_all_abs" : "profit_all_ratio";
      const av = a[key];
      const bv = b[key];
      if (av === null) return bv === null ? byName : 1;
      if (bv === null) return -1;
      return bv - av || byName;
    });
}
