const DAY_MS = 24 * 60 * 60 * 1000;

function planFromRecord(record) {
  return record?.plan || record || {};
}

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

export function recentSpending(records = [], now = new Date(), days = 30) {
  const cutoff = now.getTime() - days * DAY_MS;
  return records.reduce((total, record) => {
    const savedAt = Date.parse(record?.saved_at || "");
    if (Number.isFinite(savedAt) && savedAt < cutoff) return total;
    return total + Math.max(0, finiteNumber(planFromRecord(record).cost));
  }, 0);
}

export function recentPrizeWinnings(reviewItems = [], now = new Date(), days = 30) {
  const cutoff = now.getTime() - days * DAY_MS;
  return reviewItems.reduce((total, item) => {
    const savedAt = Date.parse(item?.saved_at || "");
    if (Number.isFinite(savedAt) && savedAt < cutoff) return total;
    const result = item?.result || item || {};
    if (result.prize_amount_complete !== true) return total;
    return total + Math.max(0, finiteNumber(result.prize_amount));
  }, 0);
}

export function cumulativeSpending(records = []) {
  let total = 0;
  return [...records]
    .sort((left, right) => Date.parse(left?.saved_at || 0) - Date.parse(right?.saved_at || 0))
    .map((record, index) => {
      const plan = planFromRecord(record);
      total += Math.max(0, finiteNumber(plan.cost));
      return {
        issue: plan.recommended_issue || record.latest_issue || index + 1,
        value: total,
        cost: finiteNumber(plan.cost),
      };
    });
}

export function hasEscalationPattern(records = [], currentCost = 0) {
  const costs = [...records]
    .sort((left, right) => Date.parse(left?.saved_at || 0) - Date.parse(right?.saved_at || 0))
    .map((record) => finiteNumber(planFromRecord(record).cost))
    .filter((cost) => cost > 0)
    .slice(-3);
  if (currentCost > 0) costs.push(currentCost);
  const recent = costs.slice(-3);
  return recent.length === 3 && recent[0] < recent[1] && recent[1] < recent[2];
}

export function buildDecisionBrief({
  plan,
  budget,
  principal,
  periodCap,
  budgetRiskEnabled = true,
  records = [],
  reviewItems = [],
  backtest,
  capital,
  now = new Date(),
}) {
  if (!plan) return null;

  const cost = Math.max(0, finiteNumber(plan.cost));
  const riskEnabled = budgetRiskEnabled !== false;
  const safeBudget = Math.max(0, finiteNumber(budget, plan?.budget_analysis?.budget || cost));
  const safePrincipal = Math.max(0, finiteNumber(principal));
  const safePeriodCap = Math.max(0, finiteNumber(periodCap, safePrincipal * 0.1));
  const periodSpent = recentSpending(records, now);
  const reviewedPrize = recentPrizeWinnings(reviewItems, now);
  const periodPrize = Math.max(reviewedPrize, Math.max(0, finiteNumber(capital?.last_prize)));
  const periodNetSpent = Math.max(0, round(periodSpent - periodPrize));
  const projectedPeriodSpend = periodSpent + cost;
  const projectedPeriodNetSpend = periodNetSpent + cost;
  const budgetUtilization = safeBudget ? round((cost / safeBudget) * 100, 1) : 0;
  const principalExposure = safePrincipal ? round((cost / safePrincipal) * 100, 2) : 0;
  const periodUtilization = safePeriodCap ? round((projectedPeriodNetSpend / safePeriodCap) * 100, 1) : 0;
  const overBudget = riskEnabled && safeBudget > 0 && cost > safeBudget;
  const overPeriodCap = riskEnabled && safePeriodCap > 0 && projectedPeriodNetSpend > safePeriodCap;
  const escalating = riskEnabled && hasEscalationPattern(records, cost);
  const levelUnits = finiteNumber(capital?.level_units, 1);
  const unprofitableStepUp = riskEnabled && levelUnits > 1 && finiteNumber(capital?.round_profit) <= 0;

  const signals = [];
  if (overBudget) signals.push(`方案超出本期预算 ${round(cost - safeBudget)} 元`);
  if (overPeriodCap) signals.push(`计入本期后，近30日净投入将超过周期上限 ${round(projectedPeriodNetSpend - safePeriodCap)} 元`);
  if (escalating) signals.push("最近三次方案费用连续上升，存在追投倾向");
  if (unprofitableStepUp) signals.push("当前处于加注级别，但上一轮没有形成净盈利");
  if (riskEnabled && principalExposure > 5) signals.push(`单次投入占本金 ${principalExposure}%，暴露偏高`);
  else if (riskEnabled && principalExposure > 2) signals.push(`单次投入占本金 ${principalExposure}%，需要留意`);

  let riskLevel = "低";
  let riskTone = "safe";
  let action = "可按当前预算执行，开奖后复盘，不因未中奖追加。";
  const blockSave = overBudget || unprofitableStepUp;
  if (!riskEnabled) {
    riskLevel = "已关闭";
    riskTone = "off";
    action = "预算风险提醒已关闭，本次仅统计方案费用，不作风险判断。";
  } else if (blockSave) {
    riskLevel = "高";
    riskTone = "stop";
    action = "建议暂停或缩减方案，先恢复到基础预算。";
  } else if (overPeriodCap || escalating) {
    riskLevel = "高";
    riskTone = "watch";
    action = "已触发风险提醒，仍可继续生成和保存；请确认净投入上限，不要临时加码。";
  } else if (signals.length > 0 || periodUtilization >= 80) {
    riskLevel = "中";
    riskTone = "watch";
    action = "可以继续，但不要提高倍率或临时追加预算。";
  }

  const summary = backtest?.summary || {};
  const baseline = backtest?.baseline || {};
  const periods = finiteNumber(summary.periods);
  const historyMessage = periods > 0
    ? `过去 ${periods} 期滚动回测中，规则方案命中记录率 ${finiteNumber(summary.record_hit_rate)}%，随机对照 ${finiteNumber(baseline.record_hit_rate)}%。这只是历史匹配统计，不代表未来收益。`
    : "尚无可用回测结果，不能据此判断长期表现。";

  const coverageLabel = plan.mode === "dantuo"
    ? `组合覆盖 ${finiteNumber(plan.tickets)} 注`
    : plan.mode === "batch"
      ? `多玩法合计 ${finiteNumber(plan.tickets)} 注`
      : plan.mode === "compound"
        ? `复式展开 ${finiteNumber(plan.tickets)} 注`
        : plan.mode === "package"
          ? `套餐展开 ${finiteNumber(plan.tickets)} 注`
          : `${finiteNumber(plan.tickets)} 注分散单式`;

  return {
    cost,
    budget: safeBudget,
    budget_utilization: budgetUtilization,
    principal_exposure: principalExposure,
    period_spent: periodSpent,
    period_prize: periodPrize,
    period_net_spent: periodNetSpent,
    period_cap: safePeriodCap,
    projected_period_spend: projectedPeriodSpend,
    projected_period_net_spend: projectedPeriodNetSpend,
    period_utilization: periodUtilization,
    coverage_label: coverageLabel,
    multiplier: Math.max(1, finiteNumber(plan.multiplier, 1)),
    risk_enabled: riskEnabled,
    risk_level: riskLevel,
    risk_tone: riskTone,
    signals: riskEnabled
      ? (signals.length ? signals : ["未发现超预算、连续加码或高资金暴露"])
      : ["预算风险提醒已关闭；本期支出上限仍用于控制生成费用"],
    escalation_detected: escalating,
    block_save: blockSave,
    history_message: historyMessage,
    action,
    guardrails: riskEnabled
      ? [
          `本期支出上限 ${safeBudget} 元`,
          `近30日投入上限 ${safePeriodCap} 元`,
          "未中奖不加码，只有本轮净盈利后才允许升级",
        ]
      : ["预算风险提醒已关闭"],
  };
}
