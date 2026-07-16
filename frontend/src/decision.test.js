import assert from "node:assert/strict";
import test from "node:test";

import { buildDecisionBrief, cumulativeSpending, hasEscalationPattern, recentPrizeWinnings, recentSpending } from "./decision.js";

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

test("已确认奖金抵扣近30日成本并允许继续生成保存", () => {
  const records = [
    { saved_at: "2026-07-05T00:00:00Z", plan: { cost: 80 } },
  ];
  const reviewItems = [
    { saved_at: "2026-07-05T00:00:00Z", prize_amount: 60, prize_amount_complete: true },
  ];
  assert.equal(recentPrizeWinnings(reviewItems, new Date("2026-07-13T00:00:00Z")), 60);
  const brief = buildDecisionBrief({
    plan: basePlan,
    budget: 20,
    principal: 1000,
    periodCap: 50,
    records,
    reviewItems,
    capital: { level_units: 1, round_profit: 0, last_prize: 0 },
    now: new Date("2026-07-13T00:00:00Z"),
  });
  assert.equal(brief.period_net_spent, 20);
  assert.equal(brief.projected_period_net_spend, 40);
  assert.equal(brief.block_save, false);
  assert.equal(brief.risk_tone, "watch");
});

test("超过净投入周期上限只报警不阻断保存", () => {
  const brief = buildDecisionBrief({
    plan: basePlan,
    budget: 20,
    principal: 1000,
    periodCap: 10,
    records: [],
    capital: { level_units: 1, round_profit: 0 },
  });
  assert.equal(brief.risk_level, "高");
  assert.equal(brief.risk_tone, "watch");
  assert.equal(brief.block_save, false);
  assert.match(brief.action, /继续生成和保存/);
});
