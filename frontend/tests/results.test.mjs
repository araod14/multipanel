import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

// Exercise the actual TypeScript helper with the compiler already used by this app.
const source = await readFile(new URL("../src/lib/results.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2021 },
});
const { filterAccounts } = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
const accounts = [
  { username: "zeta", dry_run: false, profit_all_abs: null, profit_all_ratio: null },
  { username: "Beta", dry_run: true, profit_all_abs: -12, profit_all_ratio: -0.03 },
  { username: "alfa", dry_run: false, profit_all_abs: 0, profit_all_ratio: 0 },
  { username: "delta", dry_run: true, profit_all_abs: 25, profit_all_ratio: 0.05 },
];
const names = (rows) => rows.map((a) => a.username);

test("default alphabetical order does not mutate the API payload", () => {
  const original = [...accounts];
  assert.deepEqual(names(filterAccounts(accounts, "", "all", "name")), ["alfa", "Beta", "delta", "zeta"]);
  assert.deepEqual(accounts, original);
});
test("search ignores case and trims whitespace", () => {
  assert.deepEqual(names(filterAccounts(accounts, "  BE  ", "all", "name")), ["Beta"]);
});
test("mode filter can be combined with search", () => {
  assert.deepEqual(names(filterAccounts(accounts, "", "live", "name")), ["alfa", "zeta"]);
  assert.deepEqual(names(filterAccounts(accounts, "ta", "dry", "name")), ["Beta", "delta"]);
  assert.deepEqual(filterAccounts(accounts, "Beta", "live", "name"), []);
});
test("profit and ROI sort descending with zero before negative and missing last", () => {
  for (const order of ["profit", "roi"]) {
    assert.deepEqual(names(filterAccounts(accounts, "", "all", order)), ["delta", "alfa", "Beta", "zeta"]);
  }
});
test("ties and missing values use alphabetical ordering", () => {
  const rows = [
    { ...accounts[0], username: "b" }, { ...accounts[0], username: "a" },
    { ...accounts[2], username: "d" }, { ...accounts[2], username: "c" },
  ];
  assert.deepEqual(names(filterAccounts(rows, "", "all", "profit")), ["c", "d", "a", "b"]);
});
test("empty accounts and searches with no matches return an empty list", () => {
  assert.deepEqual(filterAccounts([], "", "all", "name"), []);
  assert.deepEqual(filterAccounts(accounts, "unknown", "all", "roi"), []);
});
