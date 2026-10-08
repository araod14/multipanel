import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createRequire } from "node:module";
import vm from "node:vm";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const source = await readFile(new URL("../src/components/StatusBadge.tsx", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2021, jsx: ts.JsxEmit.ReactJSX },
});
const exports = {};
vm.runInNewContext(outputText, { exports, require: createRequire(import.meta.url) });
const baseline = {
  tradingview_guard_enabled: true,
  tradingview_paused: false,
  manual_paused: false,
  entry_pause_managed: false,
  entry_pause_pending: false,
  trading_enabled: true,
  tradingview_evaluation: null,
};
const render = (patch = {}) => renderToStaticMarkup(
  React.createElement(exports.TradingViewGuardStatus, { bot: { ...baseline, ...patch } }),
);

test("enabled indicator remains active for a stopped bot", () => {
  assert.match(render({ trading_enabled: false }), /Protección TradingView: activa/);
});
test("disabled protection displays inactive independently of a stored pause", () => {
  const html = render({ tradingview_guard_enabled: false, tradingview_paused: true });
  assert.match(html, /Protección TradingView: inactiva/);
  assert.doesNotMatch(html, /Compras pausadas por TradingView/);
});
test("automatic pause and enabled indicator are separate", () => {
  const html = render({ tradingview_paused: true, entry_pause_managed: true });
  assert.match(html, /Protección TradingView: activa/);
  assert.match(html, /Compras pausadas por TradingView/);
});
test("failed pause does not claim the command succeeded", () => {
  const html = render({ tradingview_paused: true, entry_pause_managed: true, entry_pause_pending: true });
  assert.match(html, /Pausa por TradingView pendiente/);
  assert.doesNotMatch(html, /Compras pausadas por TradingView/);
});
test("manual pause is distinguished from the automatic pause", () => {
  const html = render({ tradingview_paused: true, manual_paused: true, entry_pause_managed: true });
  assert.match(html, /Pausa manual/);
  assert.doesNotMatch(html, /Compras pausadas por TradingView/);
});
test("missing data keeps the enabled indicator and shows the full denominator", () => {
  const html = render({ tradingview_evaluation: {
    checked_at: "2026-10-08T12:00:00Z", exchange: "kraken", timeframe: "4h",
    total: 4, buy: 2, sell: 0, neutral: 1, missing: 1, data_complete: false, reason: "missing_data",
  } });
  assert.match(html, /Protección TradingView: activa/);
  assert.match(html, /Sin datos completos/);
  assert.match(html, /Compra 2\/4/);
  assert.match(html, /kraken · 4h/);
  assert.match(html, /Última evaluación/);
});
