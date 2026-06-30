const HISTORY = [
  ["2025001", "2025-01-01", [3, 7, 18, 22, 31], [4, 11]],
  ["2025002", "2025-01-03", [1, 9, 16, 24, 35], [2, 8]],
  ["2025003", "2025-01-06", [5, 12, 18, 27, 33], [3, 10]],
  ["2025004", "2025-01-08", [2, 7, 14, 23, 31], [1, 11]],
  ["2025005", "2025-01-10", [6, 13, 19, 28, 34], [5, 12]],
  ["2025006", "2025-01-13", [4, 11, 18, 25, 30], [3, 9]],
  ["2025007", "2025-01-15", [7, 15, 20, 26, 32], [6, 11]],
  ["2025008", "2025-01-17", [3, 10, 17, 24, 35], [2, 7]],
  ["2025009", "2025-01-20", [8, 14, 21, 29, 34], [4, 10]],
  ["2025010", "2025-01-22", [1, 7, 18, 23, 31], [3, 11]],
  ["2025011", "2025-01-24", [5, 12, 19, 27, 33], [1, 8]],
  ["2025012", "2025-01-27", [2, 9, 16, 25, 30], [5, 12]],
  ["2025013", "2025-01-29", [6, 13, 20, 28, 35], [2, 9]],
  ["2025014", "2025-01-31", [4, 11, 17, 24, 32], [6, 10]],
  ["2025015", "2025-02-03", [7, 14, 18, 26, 34], [3, 11]],
  ["2025016", "2025-02-05", [3, 10, 21, 29, 31], [4, 12]],
  ["2025017", "2025-02-07", [8, 15, 19, 27, 33], [1, 7]],
  ["2025018", "2025-02-10", [1, 12, 16, 23, 35], [5, 9]],
  ["2025019", "2025-02-12", [5, 13, 20, 28, 34], [2, 11]],
  ["2025020", "2025-02-14", [2, 9, 18, 25, 30], [3, 10]],
  ["2025021", "2025-02-17", [6, 14, 21, 29, 32], [4, 8]],
  ["2025022", "2025-02-19", [4, 11, 17, 24, 31], [6, 12]],
  ["2025023", "2025-02-21", [7, 15, 19, 26, 33], [1, 11]],
  ["2025024", "2025-02-24", [3, 10, 18, 27, 35], [5, 9]],
  ["2025025", "2025-02-26", [8, 12, 20, 28, 34], [2, 10]],
  ["2025026", "2025-02-28", [1, 9, 16, 23, 30], [3, 7]],
  ["2025027", "2025-03-03", [5, 13, 21, 29, 32], [4, 11]],
  ["2025028", "2025-03-05", [2, 14, 17, 24, 31], [6, 8]],
  ["2025029", "2025-03-07", [6, 11, 19, 26, 33], [1, 12]],
  ["2025030", "2025-03-10", [4, 15, 18, 27, 35], [3, 9]],
].map(([issue, date, front, back]) => ({ issue, date, front, back }));

const STRATEGY_LABELS = {
  conservative: "保守",
  balanced: "均衡",
  aggressive: "激进",
};

function countValues(values, min, max) {
  const counts = new Map(Array.from({ length: max - min + 1 }, (_, index) => [index + min, 0]));
  values.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return counts;
}

function normalize(value, maxValue) {
  return maxValue <= 0 ? 0 : Math.round((value / maxValue) * 10000) / 100;
}

function balanceScore(number) {
  const oddScore = number % 2 === 1 ? 100 : 92;
  const sizeScore = number >= 10 && number <= 28 ? 100 : 84;
  const edgePenalty = [1, 2, 34, 35].includes(number) ? 8 : 0;
  return Math.max(0, Math.round((((oddScore + sizeScore) / 2) - edgePenalty) * 100) / 100);
}

function ratioLabel(left, total) {
  return `${left}:${total - left}`;
}

function buildTrends(window = 100) {
  const recent = HISTORY.slice(-window);
  const frontCounts = countValues(recent.flatMap((row) => row.front), 1, 35);
  const backCounts = countValues(recent.flatMap((row) => row.back), 1, 12);
  const omissions = Array.from({ length: 35 }, (_, index) => {
    const number = index + 1;
    const reverseIndex = [...HISTORY].reverse().findIndex((row) => row.front.includes(number));
    return { number, missing: reverseIndex === -1 ? HISTORY.length : reverseIndex };
  });
  const oddEven = new Map();
  const bigSmall = new Map();
  const sums = HISTORY.map((row) => row.front.reduce((sum, number) => sum + number, 0));

  HISTORY.forEach((row) => {
    const odd = row.front.filter((number) => number % 2 === 1).length;
    const small = row.front.filter((number) => number <= 17).length;
    oddEven.set(ratioLabel(odd, 5), (oddEven.get(ratioLabel(odd, 5)) || 0) + 1);
    bigSmall.set(ratioLabel(small, 5), (bigSmall.get(ratioLabel(small, 5)) || 0) + 1);
  });

  return {
    window: Math.min(window, HISTORY.length),
    hot_front: Array.from(frontCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    hot_back: Array.from(backCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    omissions,
    odd_even: Array.from(oddEven, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    big_small: Array.from(bigSmall, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    sum_values: HISTORY.slice(-30).map((row) => ({ issue: row.issue, value: row.front.reduce((sum, number) => sum + number, 0) })),
    sum_range: {
      min: Math.min(...sums),
      max: Math.max(...sums),
      avg: Math.round((sums.reduce((sum, value) => sum + value, 0) / sums.length) * 100) / 100,
    },
  };
}

function scoreFront(trends) {
  const heatByNumber = new Map(trends.hot_front.map((item) => [item.number, item.count]));
  const missingByNumber = new Map(trends.omissions.map((item) => [item.number, item.missing]));
  const maxHeat = Math.max(...heatByNumber.values());
  const maxMissing = Math.max(...missingByNumber.values());
  return Array.from({ length: 35 }, (_, index) => {
    const number = index + 1;
    const heat = normalize(heatByNumber.get(number) || 0, maxHeat);
    const missing = normalize(missingByNumber.get(number) || 0, maxMissing);
    const balanced = balanceScore(number);
    const total = Math.round((heat * 0.4 + missing * 0.3 + balanced * 0.3) * 100) / 100;
    return {
      number,
      heat_count: heatByNumber.get(number) || 0,
      missing_periods: missingByNumber.get(number) || 0,
      heat_score: heat,
      missing_score: missing,
      balance_score: balanced,
      total_score: total,
      explanation: `热度${heat}分、遗漏${missing}分、均衡${balanced}分；综合评分按 0.4/0.3/0.3 加权得到 ${total}。`,
    };
  }).sort((a, b) => b.total_score - a.total_score || a.number - b.number)
    .map((row, index) => ({ ...row, rank: index + 1 }));
}

function scoreBack(trends) {
  const maxHeat = Math.max(...trends.hot_back.map((item) => item.count));
  return trends.hot_back.map((item) => ({ number: item.number, score: normalize(item.count, maxHeat) }));
}

function formatNumbers(numbers) {
  return numbers.map((number) => String(number).padStart(2, "0"));
}

function planScore(numbers, rows) {
  const scoreByNumber = new Map(rows.map((row) => [row.number, row.total_score]));
  return Math.round(numbers.reduce((sum, number) => sum + (scoreByNumber.get(number) || 0), 0) * 100) / 100;
}

function planExplanations(numbers, rows) {
  const byNumber = new Map(rows.map((row) => [row.number, row.explanation]));
  return numbers.slice(0, 5).map((number) => `${String(number).padStart(2, "0")}：${byNumber.get(number) || ""}`);
}

function buildSinglePlan(budget, strategy, scores, backScores) {
  const ticketCount = Math.max(1, Math.floor(budget / 2));
  const rankedFront = scores.map((row) => row.number);
  const rankedBack = backScores.map((row) => row.number);
  const items = Array.from({ length: ticketCount }, (_, index) => {
    const frontPool = rankedFront.slice(index).concat(rankedFront.slice(0, index));
    const backPool = rankedBack.slice(index).concat(rankedBack.slice(0, index));
    const front = frontPool.slice(0, 5).sort((a, b) => a - b);
    const back = backPool.slice(0, 2).sort((a, b) => a - b);
    return {
      front,
      back,
      front_display: formatNumbers(front),
      back_display: formatNumbers(back),
      score: planScore(front, scores),
      explanation: planExplanations(front, scores),
    };
  });
  const score = Math.round(items.reduce((sum, item) => sum + item.score, 0) * 100) / 100;
  return {
    mode: "single",
    strategy,
    cost: ticketCount * 2,
    tickets: ticketCount,
    items,
    score,
    reason: `${STRATEGY_LABELS[strategy] || "均衡"}策略生成单式方案；综合评分 ${score}，费用不超过预算。`,
  };
}

function buildDantuoPlan(budget, strategy, scores, backScores) {
  const rankedFront = scores.map((row) => row.number);
  const rankedBack = backScores.map((row) => row.number);
  const danCount = strategy === "aggressive" ? 3 : 2;
  const tuoCount = budget >= 30 ? 6 : 5;
  const frontDan = rankedFront.slice(0, danCount).sort((a, b) => a - b);
  const frontTuo = rankedFront.slice(danCount, danCount + tuoCount).sort((a, b) => a - b);
  const back = rankedBack.slice(0, strategy === "aggressive" && budget >= 40 ? 3 : 2).sort((a, b) => a - b);
  const tickets = budget >= 30 ? 15 : 10;
  const cost = Math.min(budget, tickets * 2);
  const score = planScore(frontDan.concat(frontTuo), scores);
  return {
    mode: "dantuo",
    strategy,
    cost,
    tickets: Math.floor(cost / 2),
    front_dan: frontDan,
    front_tuo: frontTuo,
    back,
    front_dan_display: formatNumbers(frontDan),
    front_tuo_display: formatNumbers(frontTuo),
    back_display: formatNumbers(back),
    score,
    explanation: planExplanations(frontDan.concat(frontTuo), scores),
    reason: `${STRATEGY_LABELS[strategy] || "均衡"}策略在预算内选择胆拖结构；综合评分 ${score}，预算占用 ${Math.round((cost / budget) * 1000) / 10}%。`,
  };
}

function buildCapital(lastPrize = 0, principal = 1000, balance, levelUnits = 1) {
  const startBalance = balance === "" || balance === null || balance === undefined ? principal : Number(balance);
  const stake = Number(levelUnits) * 2;
  const prize = Math.max(0, Number(lastPrize) || 0);
  const endingBalance = Math.round((startBalance - stake + prize) * 100) / 100;
  const roundProfit = prize - stake;
  const nextUnits = roundProfit > 0 ? Math.min(4, Number(levelUnits) * 2) : 1;
  const maxDrawdown = principal > 0 ? Math.round(Math.max(0, ((principal - endingBalance) / principal) * 100) * 100) / 100 : 0;
  return {
    principal,
    balance: endingBalance,
    profit: Math.round((endingBalance - principal) * 100) / 100,
    interrupted_profit: roundProfit <= 0 ? Math.max(0, startBalance - principal) : 0,
    max_drawdown: maxDrawdown,
    current_drawdown: maxDrawdown,
    level: `${levelUnits}注`,
    level_units: Number(levelUnits),
    next_level: `${nextUnits}注`,
    next_level_units: nextUnits,
    stake,
    last_prize: prize,
    round_profit: roundProfit,
    total_invested: stake,
    total_prize: prize,
    transition_explanation: roundProfit > 0
      ? `${levelUnits}注 -> ${nextUnits}注：本轮盈利，按 Anti-Martingale 赢后加码。`
      : `${levelUnits}注 -> 1注：本轮未盈利，回到基础下注控制回撤。`,
  };
}

export function getDemoScenes() {
  return Promise.resolve([
    { code: "DLT", name: "大乐透", module: "DLT Module", status: "已上线", description: "前区 35 选 5，后区 12 选 2", enabled: true, front: { min: 1, max: 35, pick: 5 }, back: { min: 1, max: 12, pick: 2 } },
    { code: "SSQ", name: "双色球", module: "SSQ Module", status: "开发中", description: "红球 33 选 6，蓝球 16 选 1", enabled: false, front: { min: 1, max: 33, pick: 6 }, back: { min: 1, max: 16, pick: 1 } },
    { code: "K8", name: "快乐8", module: "K8 Module", status: "规划中", description: "快乐8 场景规划中", enabled: false, front: { min: 1, max: 80, pick: 20 }, back: { min: 0, max: 0, pick: 0 } },
    { code: "CUSTOM", name: "自定义分析", module: "Custom Analysis", status: "规划中", description: "自定义号码规则与历史数据", enabled: false, front: { min: 1, max: 35, pick: 5 }, back: { min: 1, max: 12, pick: 2 } },
  ]);
}

export function getDemoDashboard({ budget = 20, lastPrize = 0, strategy = "balanced", window = 100, principal = 1000, balance = "", levelUnits = 1 }) {
  const trends = buildTrends(Number(window));
  const scoreTable = scoreFront(trends);
  const backScores = scoreBack(trends);
  const plans = strategy === "conservative"
    ? [buildSinglePlan(Number(budget), strategy, scoreTable, backScores)]
    : [buildDantuoPlan(Number(budget), strategy, scoreTable, backScores), buildSinglePlan(Number(budget), strategy, scoreTable, backScores)];
  const latest = HISTORY[HISTORY.length - 1];
  return Promise.resolve({
    scene: "DLT",
    product: { name: "策维", english_name: "Ceway", subtitle: "Digital Decision Platform", framework: "Powered by CBGO Framework", version: "v1.3 Static Demo" },
    disclaimer: "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
    history_count: HISTORY.length,
    latest_issue: latest.issue,
    data_status: {
      source: "static_demo",
      source_label: "静态演示数据",
      path: "GitHub Pages demo",
      latest_issue: latest.issue,
      latest_date: latest.date,
      is_sample: true,
      message: "当前页面运行在 GitHub Pages 静态演示模式，使用内置样例数据；正式分析请回到本地后端导入 CSV。",
    },
    top_numbers: scoreTable.slice(0, 5).map((row) => row.number),
    budget: Number(budget),
    strategy,
    window: trends.window,
    recommended_amount: Math.max(...plans.map((plan) => plan.cost)),
    capital_state: buildCapital(lastPrize, Number(principal), balance, levelUnits),
    trends,
    score_table: scoreTable,
    plans,
  });
}

export function getDemoPlan(params) {
  return getDemoDashboard(params).then((dashboard) => dashboard.plans[0]);
}

export function getDemoRecords() {
  return Promise.resolve(JSON.parse(localStorage.getItem("ceway_demo_records") || "[]"));
}

export function saveDemoRecord({ budget, strategy, latestIssue, plan }) {
  const records = JSON.parse(localStorage.getItem("ceway_demo_records") || "[]");
  const record = {
    id: `demo-${Date.now()}`,
    saved_at: new Date().toISOString(),
    budget,
    strategy,
    latest_issue: latestIssue,
    plan,
  };
  const next = [record, ...records].slice(0, 30);
  localStorage.setItem("ceway_demo_records", JSON.stringify(next));
  return Promise.resolve({ status: "ok", record, count: next.length });
}
