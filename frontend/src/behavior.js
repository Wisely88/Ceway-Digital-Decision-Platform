function plan(record) {
  return record?.plan || record || {};
}

function cost(record) {
  const value = Number(plan(record).cost || 0);
  return Number.isFinite(value) ? Math.max(0, value) : 0;
}

function escalationCount(records) {
  const costs = [...records]
    .sort((left, right) => Date.parse(left.saved_at || 0) - Date.parse(right.saved_at || 0))
    .map(cost);
  return costs.reduce((count, value, index) => count + (index >= 2 && costs[index - 2] < costs[index - 1] && costs[index - 1] < value ? 1 : 0), 0);
}

function marketPulse(issues = {}, source = "") {
  const rows = Object.entries(issues)
    .map(([issue, item]) => ({ issue, ...item }))
    .filter((item) => Number(item.sales) > 0)
    .slice(-20);
  if (!rows.length) return { available: false, label: "暂无官方销售额", source, message: "当前数据源没有可用销售额，不以论坛讨论量代替真实市场数据。", series: [] };
  const recent = rows.slice(-5);
  const previous = rows.slice(-10, -5);
  const average = (items) => items.reduce((sum, item) => sum + Number(item.sales), 0) / Math.max(1, items.length);
  const recentAverage = average(recent);
  const previousAverage = previous.length ? average(previous) : recentAverage;
  const change = previousAverage ? Math.round(((recentAverage - previousAverage) / previousAverage) * 1000) / 10 : 0;
  return {
    available: true,
    label: change >= 5 ? "参与升温" : change <= -5 ? "参与降温" : "参与平稳",
    change_percent: change,
    latest_sales: Number(rows.at(-1).sales),
    latest_issue: rows.at(-1).issue,
    source: rows.at(-1).source || source,
    message: "官方销售额只描述市场参与规模，不改变任何一注的中奖概率。",
    series: rows.map((item) => ({ issue: item.issue, sales: Number(item.sales) })),
  };
}

export function buildBehaviorProfile(records = [], review = {}, snapshot = {}, now = new Date()) {
  const cutoff = now.getTime() - 30 * 24 * 60 * 60 * 1000;
  const recent = records.filter((record) => {
    const savedAt = Date.parse(record.saved_at || "");
    return !Number.isFinite(savedAt) || savedAt >= cutoff;
  });
  const costs = records.map(cost);
  const averageCost = costs.length ? Math.round((costs.reduce((sum, value) => sum + value, 0) / costs.length) * 100) / 100 : 0;
  const maximumCost = Math.max(0, ...costs);
  const escalations = escalationCount(records);
  const highFrequency = recent.length >= 8;
  const outlier = averageCost > 0 && maximumCost >= averageCost * 2;
  const riskScore = Math.min(100, escalations * 30 + (highFrequency ? 20 : 0) + (outlier ? 20 : 0));
  const riskLevel = riskScore >= 60 ? "高" : riskScore >= 30 ? "中" : "低";
  const signals = [];
  if (escalations) signals.push(`发现 ${escalations} 次连续三期加码`);
  if (highFrequency) signals.push("近30日保存方案频次偏高");
  if (outlier) signals.push("最大单次支出达到平均支出的两倍");
  if (!signals.length) signals.push("未发现连续加码或异常高频保存");
  const summary = review.summary || {};
  return {
    engine: "可解释规则引擎",
    risk_score: riskScore,
    risk_level: riskLevel,
    metrics: {
      record_count: records.length,
      recent_count: recent.length,
      recent_cost: recent.reduce((sum, record) => sum + cost(record), 0),
      average_cost: averageCost,
      maximum_cost: maximumCost,
      dantuo_ratio: records.length ? Math.round((records.filter((record) => plan(record).mode === "dantuo").length / records.length) * 1000) / 10 : 0,
      escalation_count: escalations,
      reviewed_count: summary.reviewed || 0,
      historical_roi: summary.roi_complete ? summary.roi : null,
    },
    signals,
    action: riskLevel === "高" ? "暂停新增方案，恢复基础预算并等待已保存方案完成复盘。" : "保持固定预算，不因市场热度、遗漏或未中奖临时加码。",
    market: marketPulse(snapshot.issues, snapshot.source),
    disclaimer: "智能分析只解释历史投注行为与市场参与规模，不预测开奖号码或收益。",
  };
}
