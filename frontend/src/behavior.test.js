import assert from "node:assert/strict";
import test from "node:test";
import { buildBehaviorProfile } from "./behavior.js";

test("行为分析识别连续加码并使用官方销售额", () => {
  const records = [10, 20, 40].map((cost, index) => ({ saved_at: `2026-07-0${index + 1}T00:00:00Z`, plan: { cost, mode: "dantuo" } }));
  const issues = Object.fromEntries([100, 100, 100, 100, 100, 120, 125, 130, 135, 140].map((sales, index) => [`${index + 1}`, { sales, source: "官方接口" }]));
  const result = buildBehaviorProfile(records, { summary: {} }, { source: "官方接口", issues }, new Date("2026-07-10T00:00:00Z"));
  assert.equal(result.risk_level, "中");
  assert.equal(result.metrics.escalation_count, 1);
  assert.equal(result.market.label, "参与升温");
});

test("无记录时保持低风险且不伪造市场热度", () => {
  const result = buildBehaviorProfile([], { summary: {} }, { issues: {} });
  assert.equal(result.risk_level, "低");
  assert.equal(result.market.available, false);
});
