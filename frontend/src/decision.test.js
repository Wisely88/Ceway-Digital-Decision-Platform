import assert from "node:assert/strict";
import test from "node:test";

import { buildDecisionBrief, cumulativeSpending, hasEscalationPattern, recentSpending } from "./decision.js";

const basePlan = {
  mode: "dantuo",
  cost: 20,
  tickets: 10,
  budget_analysis: { budget: 20 },
};

test("预算内且没有连续加码时给出低风险结论", () => {
  const brief = buildDecisionBrief({
    plan: basePlan,
    budget: 20,
    principal: 1000,
    periodCap: 200,
    records: [],
    capital: { level_units: 1, round_profit: -2 },
    backtest: { summary: { periods: 100, record_hit_rate: 12 }, baseline: { record_hit_rate: 11 } },
  });

  assert.equal(brief.risk_level, "低");
  assert.equal(brief.coverage_label, "组合覆盖 10 注");
  assert.equal(brief.multiplier, 1);
  assert.equal(brief.principal_exposure, 2);
});

test("超预算或超过周期上限时建议暂停", () => {
  const brief = buildDecisionBrief({
    plan: { ...basePlan, cost: 60, tickets: 30 },
    budget: 20,
    principal: 1000,
    periodCap: 50,
    records: [],
    capital: { level_units: 1, round_profit: -2 },
  });

  assert.equal(brief.risk_level, "高");
  assert.match(brief.action, /暂停|缩减/);
  assert.ok(brief.signals.some((signal) => signal.includes("超出本期预算")));
});

test("连续三次提高方案费用会触发追投提醒", () => {
  const records = [
    { saved_at: "2026-07-01T00:00:00Z", plan: { cost: 10 } },
    { saved_at: "2026-07-02T00:00:00Z", plan: { cost: 20 } },
  ];
  assert.equal(hasEscalationPattern(records, 30), true);

  const brief = buildDecisionBrief({
    plan: { ...basePlan, cost: 30 },
    budget: 30,
    principal: 2000,
    periodCap: 200,
    records,
    capital: { level_units: 1, round_profit: -2 },
  });
  assert.equal(brief.escalation_detected, true);
  assert.equal(brief.risk_level, "高");
});

test("近30日投入和累计投入都来自保存记录", () => {
  const records = [
    { saved_at: "2026-05-01T00:00:00Z", plan: { cost: 50, recommended_issue: "old" } },
    { saved_at: "2026-07-05T00:00:00Z", plan: { cost: 10, recommended_issue: "a" } },
    { saved_at: "2026-07-06T00:00:00Z", plan: { cost: 20, recommended_issue: "b" } },
  ];
  assert.equal(recentSpending(records, new Date("2026-07-13T00:00:00Z")), 30);
  assert.deepEqual(cumulativeSpending(records).map((item) => item.value), [50, 60, 80]);
});
