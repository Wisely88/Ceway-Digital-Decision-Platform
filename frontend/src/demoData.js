import dltHistoryCsv from "../../backend/data/dlt_history.csv?raw";
import ssqHistoryCsv from "../../backend/data/ssq_history.csv?raw";

const SAMPLE_HISTORY = [
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

const PARSED_DLT_HISTORY = dltHistoryCsv
  .trim()
  .split(/\r?\n/)
  .slice(1)
  .map((line) => {
    const [issue, date, ...values] = line.split(",");
    const numbers = values.map(Number);
    return { issue, date, front: numbers.slice(0, 5), back: numbers.slice(5, 7) };
  })
  .filter((row) => row.issue && row.front.length === 5 && row.back.length === 2);
const HISTORY = PARSED_DLT_HISTORY.length ? PARSED_DLT_HISTORY : SAMPLE_HISTORY;

const SSQ_HISTORY = ssqHistoryCsv
  .trim()
  .split(/\r?\n/)
  .slice(1)
  .map((line) => {
    const [issue, date, ...values] = line.split(",");
    const numbers = values.map(Number);
    return { issue, date, front: numbers.slice(0, 6), back: numbers.slice(6, 7) };
  })
  .filter((row) => row.issue && row.front.length === 6 && row.back.length === 1);

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

function buildTrends(window = 100, history = HISTORY) {
  const recent = history.slice(-window);
  const frontCounts = countValues(recent.flatMap((row) => row.front), 1, 35);
  const backCounts = countValues(recent.flatMap((row) => row.back), 1, 12);
  const lastSeen = new Map();
  history.forEach((row, index) => row.front.forEach((number) => lastSeen.set(number, index)));
  const omissions = Array.from({ length: 35 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    return { number, missing: seenAt === undefined ? history.length : history.length - seenAt - 1 };
  });
  const oddEven = new Map();
  const bigSmall = new Map();
  const sums = recent.map((row) => row.front.reduce((sum, number) => sum + number, 0));

  recent.forEach((row) => {
    const odd = row.front.filter((number) => number % 2 === 1).length;
    const small = row.front.filter((number) => number <= 17).length;
    oddEven.set(ratioLabel(odd, 5), (oddEven.get(ratioLabel(odd, 5)) || 0) + 1);
    bigSmall.set(ratioLabel(small, 5), (bigSmall.get(ratioLabel(small, 5)) || 0) + 1);
  });

  return {
    window: Math.min(window, history.length),
    hot_front: Array.from(frontCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    hot_back: Array.from(backCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    omissions,
    odd_even: Array.from(oddEven, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    big_small: Array.from(bigSmall, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    sum_values: recent.slice(-30).map((row) => ({ issue: row.issue, value: row.front.reduce((sum, number) => sum + number, 0) })),
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

function buildSsqTrends(window = 100, history = SSQ_HISTORY) {
  const recent = history.slice(-window);
  const frontCounts = countValues(recent.flatMap((row) => row.front), 1, 33);
  const backCounts = countValues(recent.flatMap((row) => row.back), 1, 16);
  const lastSeen = new Map();
  history.forEach((row, index) => row.front.forEach((number) => lastSeen.set(number, index)));
  const omissions = Array.from({ length: 33 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    return { number, missing: seenAt === undefined ? history.length : history.length - seenAt - 1 };
  });
  const oddEven = new Map();
  const bigSmall = new Map();
  const sums = recent.map((row) => row.front.reduce((sum, number) => sum + number, 0));
  recent.forEach((row) => {
    const odd = row.front.filter((number) => number % 2 === 1).length;
    const small = row.front.filter((number) => number <= 16).length;
    oddEven.set(ratioLabel(odd, 6), (oddEven.get(ratioLabel(odd, 6)) || 0) + 1);
    bigSmall.set(ratioLabel(small, 6), (bigSmall.get(ratioLabel(small, 6)) || 0) + 1);
  });
  return {
    window: recent.length,
    hot_front: Array.from(frontCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    hot_back: Array.from(backCounts, ([number, count]) => ({ number, count })).sort((a, b) => b.count - a.count || a.number - b.number),
    omissions,
    odd_even: Array.from(oddEven, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    big_small: Array.from(bigSmall, ([ratio, count]) => ({ ratio, count })).sort((a, b) => a.ratio.localeCompare(b.ratio)),
    sum_values: recent.slice(-30).map((row) => ({ issue: row.issue, value: row.front.reduce((sum, number) => sum + number, 0) })),
    sum_range: {
      min: Math.min(...sums),
      max: Math.max(...sums),
      avg: Math.round((sums.reduce((sum, value) => sum + value, 0) / Math.max(1, sums.length)) * 100) / 100,
    },
  };
}

function scoreSsqFront(trends) {
  const heatByNumber = new Map(trends.hot_front.map((item) => [item.number, item.count]));
  const missingByNumber = new Map(trends.omissions.map((item) => [item.number, item.missing]));
  const maxHeat = Math.max(...heatByNumber.values());
  const maxMissing = Math.max(...missingByNumber.values());
  return Array.from({ length: 33 }, (_, index) => {
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

function combination(n, k) {
  if (k < 0 || n < k) return 0;
  let value = 1;
  for (let index = 1; index <= k; index += 1) value = (value * (n - index + 1)) / index;
  return Math.round(value);
}

function buildSsqSinglePlan(budget, strategy, scores, backScores) {
  const ticketCount = Math.max(1, Math.floor(budget / 2));
  const rankedFront = scores.map((row) => row.number);
  const rankedBack = backScores.map((row) => row.number);
  const items = Array.from({ length: ticketCount }, (_, index) => {
    const front = rankedFront.slice(index).concat(rankedFront.slice(0, index)).slice(0, 6).sort((a, b) => a - b);
    const back = rankedBack.slice(index).concat(rankedBack.slice(0, index)).slice(0, 1);
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
    scene: "SSQ",
    mode: "single",
    strategy,
    cost: ticketCount * 2,
    tickets: ticketCount,
    items,
    score,
    reason: `双色球${STRATEGY_LABELS[strategy] || "均衡"}规则生成 ${ticketCount} 注分散单式，每注 1 倍。`,
  };
}

function buildSsqDantuoPlan(budget, strategy, scores, backScores) {
  const rankedFront = scores.map((row) => row.number);
  const rankedBack = backScores.map((row) => row.number);
  const candidates = [];
  for (let danCount = 1; danCount <= 5; danCount += 1) {
    for (let tuoCount = 6 - danCount; tuoCount <= 10; tuoCount += 1) {
      for (let backCount = 1; backCount <= 3; backCount += 1) {
        const tickets = combination(tuoCount, 6 - danCount) * backCount;
        const cost = tickets * 2;
        if (cost <= 0 || cost > budget) continue;
        candidates.push({ danCount, tuoCount, backCount, tickets, cost });
      }
    }
  }
  const structure = candidates.sort((left, right) => right.cost - left.cost || right.tickets - left.tickets)[0];
  if (!structure) return buildSsqSinglePlan(budget, strategy, scores, backScores);
  const frontDan = rankedFront.slice(0, structure.danCount).sort((a, b) => a - b);
  const frontTuo = rankedFront.slice(structure.danCount, structure.danCount + structure.tuoCount).sort((a, b) => a - b);
  const back = rankedBack.slice(0, structure.backCount).sort((a, b) => a - b);
  const score = planScore(frontDan.concat(frontTuo), scores);
  return {
    scene: "SSQ",
    mode: "dantuo",
    strategy,
    cost: structure.cost,
    tickets: structure.tickets,
    front_dan: frontDan,
    front_tuo: frontTuo,
    back,
    front_dan_display: formatNumbers(frontDan),
    front_tuo_display: formatNumbers(frontTuo),
    back_display: formatNumbers(back),
    score,
    explanation: planExplanations(frontDan.concat(frontTuo), scores),
    reason: `双色球胆拖按组合公式生成 ${structure.tickets} 注，每注 1 倍，费用不超过预算。`,
  };
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
  const candidates = [];
  for (let danCount = 1; danCount <= 3; danCount += 1) {
    for (let tuoCount = 5 - danCount; tuoCount <= 10; tuoCount += 1) {
      for (let backCount = 2; backCount <= 3; backCount += 1) {
        const tickets = combination(tuoCount, 5 - danCount) * combination(backCount, 2);
        const cost = tickets * 2;
        if (cost <= 0 || cost > budget) continue;
        candidates.push({ danCount, tuoCount, backCount, tickets, cost });
      }
    }
  }
  const structure = candidates.sort((left, right) => right.cost - left.cost || right.tickets - left.tickets)[0];
  if (!structure) return buildSinglePlan(budget, strategy, scores, backScores);
  const frontDan = rankedFront.slice(0, structure.danCount).sort((a, b) => a - b);
  const frontTuo = rankedFront.slice(structure.danCount, structure.danCount + structure.tuoCount).sort((a, b) => a - b);
  const back = rankedBack.slice(0, structure.backCount).sort((a, b) => a - b);
  const score = planScore(frontDan.concat(frontTuo), scores);
  return {
    mode: "dantuo",
    strategy,
    cost: structure.cost,
    tickets: structure.tickets,
    front_dan: frontDan,
    front_tuo: frontTuo,
    back,
    front_dan_display: formatNumbers(frontDan),
    front_tuo_display: formatNumbers(frontTuo),
    back_display: formatNumbers(back),
    score,
    explanation: planExplanations(frontDan.concat(frontTuo), scores),
    reason: `${STRATEGY_LABELS[strategy] || "均衡"}策略在预算内选择胆拖结构；综合评分 ${score}，预算占用 ${Math.round((structure.cost / budget) * 1000) / 10}%。`,
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
    { code: "SSQ", name: "双色球", module: "SSQ Module", status: "已上线", description: "红球 33 选 6，蓝球 16 选 1", enabled: true, front: { min: 1, max: 33, pick: 6 }, back: { min: 1, max: 16, pick: 1 } },
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
  const recommendedIssue = String(Number(latest.issue) + 1).padStart(latest.issue.length, "0");
  plans.forEach((plan) => {
    plan.scene = "DLT";
    plan.based_on_issue = latest.issue;
    plan.recommended_issue = recommendedIssue;
    plan.recommendation_label = `基于第 ${latest.issue} 期开奖数据，生成第 ${recommendedIssue} 期规则建议。`;
    plan.play_name = "大乐透";
    plan.play_labels = {
      front: "前区",
      back: "后区",
      dan: "前区胆码",
      tuo: "前区拖码",
      single: "单式票",
      rule: "大乐透：前区 35 选 5，后区 12 选 2；每注按 1 倍、2 元计算。",
    };
    plan.budget_analysis = {
      budget: Number(budget),
      cost: plan.cost,
      unused: Math.max(0, Number(budget) - plan.cost),
      utilization: Math.round((plan.cost / Number(budget)) * 1000) / 10,
      explanation: plan.cost === Number(budget) ? "本方案刚好使用本期预算。" : `组合公式决定当前使用 ${plan.cost} 元，剩余预算不强行加注。`,
    };
  });
  return Promise.resolve({
    scene: "DLT",
    product: { name: "策维", english_name: "Ceway", subtitle: "Digital Decision Platform", framework: "Powered by CBGO Framework", version: "v1.6 Static Demo" },
    disclaimer: "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
    history_count: HISTORY.length,
    latest_issue: latest.issue,
    recommended_issue: recommendedIssue,
    data_status: {
      source: "static_demo",
      source_label: "静态演示数据",
      path: "内置 DLT CSV 快照",
      latest_issue: latest.issue,
      latest_date: latest.date,
      is_sample: false,
      message: "当前页面运行在 GitHub Pages 静态演示模式，使用发布时打包的完整 DLT CSV 快照。",
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

export function getDemoSsqDashboard({ budget = 20, lastPrize = 0, strategy = "balanced", window = 100, principal = 1000, balance = "", levelUnits = 1 }) {
  const trends = buildSsqTrends(Number(window));
  const scoreboard = scoreSsqFront(trends);
  const backScoreboard = scoreBack(trends);
  const plans = strategy === "conservative"
    ? [buildSsqSinglePlan(Number(budget), strategy, scoreboard, backScoreboard)]
    : [buildSsqDantuoPlan(Number(budget), strategy, scoreboard, backScoreboard), buildSsqSinglePlan(Number(budget), strategy, scoreboard, backScoreboard)];
  const latest = SSQ_HISTORY.at(-1);
  const recommendedIssue = String(Number(latest.issue) + 1).padStart(latest.issue.length, "0");
  plans.forEach((plan) => {
    plan.based_on_issue = latest.issue;
    plan.recommended_issue = recommendedIssue;
    plan.recommendation_label = `基于第 ${latest.issue} 期开奖数据，生成第 ${recommendedIssue} 期规则建议。`;
    plan.play_name = "双色球";
    plan.play_labels = {
      front: "红球",
      back: "蓝球",
      dan: "红球胆码",
      tuo: "红球拖码",
      single: "单式票",
      rule: "双色球：红球 33 选 6，蓝球 16 选 1；每注按 1 倍、2 元计算。",
    };
    plan.budget_analysis = {
      budget: Number(budget),
      cost: plan.cost,
      unused: Math.max(0, Number(budget) - plan.cost),
      utilization: Math.round((plan.cost / Number(budget)) * 1000) / 10,
      explanation: plan.cost === Number(budget) ? "本方案刚好使用本期预算。" : `组合公式决定当前使用 ${plan.cost} 元，剩余预算不强行加注。`,
    };
  });
  return Promise.resolve({
    scene: "SSQ",
    product: { name: "策维", english_name: "Ceway", subtitle: "Digital Decision Platform", framework: "Powered by CBGO Framework", version: "v1.6 Static Demo" },
    disclaimer: "策维不预测开奖结果，不承诺提高中奖概率；静态演示只用于验证流程。",
    history_count: SSQ_HISTORY.length,
    latest_issue: latest.issue,
    recommended_issue: recommendedIssue,
    plans,
    trends,
    scoreboard,
    back_scoreboard: backScoreboard,
    top_front: scoreboard.slice(0, 6).map((row) => row.number),
    capital: buildCapital(lastPrize, Number(principal), balance, levelUnits),
    storage: {
      storage: "static_demo",
      path: "内置 SSQ CSV 快照",
      draw_count: SSQ_HISTORY.length,
      latest_issue: latest.issue,
      latest_date: latest.date,
      quality: { level: "snapshot", label: "静态快照", message: "数据随 GitHub Pages 发布版本更新，不会在浏览器内自动联网。", missing_count: 0, missing_issues: [] },
    },
  });
}

export function getDemoSsqPlan(params) {
  return getDemoSsqDashboard(params).then((dashboard) => dashboard.plans[0]);
}

export function getDemoRecords() {
  return Promise.resolve(JSON.parse(localStorage.getItem("ceway_demo_records") || "[]"));
}

export function getDemoSsqRecords() {
  return Promise.resolve(JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]"));
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

export function saveDemoSsqRecord({ budget, strategy, latestIssue, plan }) {
  const records = JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]");
  const record = {
    id: `demo-ssq-${Date.now()}`,
    saved_at: new Date().toISOString(),
    budget,
    strategy,
    latest_issue: latestIssue,
    plan,
  };
  const next = [record, ...records].slice(0, 30);
  localStorage.setItem("ceway_demo_ssq_records", JSON.stringify(next));
  return Promise.resolve({ status: "ok", record, count: next.length });
}

function prizeLabel(frontHits, backHits) {
  if (frontHits === 5 && backHits === 2) return "一等奖";
  if (frontHits === 5 && backHits === 1) return "二等奖";
  if (frontHits === 5) return "三等奖";
  if (frontHits === 4 && backHits === 2) return "四等奖";
  if (frontHits === 4 && backHits === 1) return "五等奖";
  if (frontHits === 3 && backHits === 2) return "六等奖";
  if (frontHits === 4) return "七等奖";
  if ((frontHits === 3 && backHits === 1) || (frontHits === 2 && backHits === 2)) return "八等奖";
  if ((frontHits === 3 && backHits === 0) || (frontHits === 2 && backHits === 1) || (frontHits <= 1 && backHits === 2)) return "九等奖";
  return "未命中固定奖级";
}

function compareTicket(front, back, draw) {
  const frontHits = front.filter((number) => draw.front.includes(number)).length;
  const backHits = back.filter((number) => draw.back.includes(number)).length;
  return {
    front,
    back,
    front_hits: frontHits,
    back_hits: backHits,
    hit_label: `${frontHits}+${backHits}`,
    prize_label: prizeLabel(frontHits, backHits),
  };
}

function nextDemoDraw(issue) {
  if (!issue) return HISTORY[HISTORY.length - 1];
  const index = HISTORY.findIndex((row) => row.issue === issue);
  return index >= 0 && index + 1 < HISTORY.length ? HISTORY[index + 1] : null;
}

function reviewDemoPlan(plan, draw) {
  const details = plan.mode === "dantuo"
    ? [compareTicket(
      [...(plan.front_dan || []), ...(plan.front_tuo || [])].slice(0, 5),
      (plan.back || []).slice(0, 2),
      draw,
    )]
    : (plan.items || []).map((item, index) => ({ ticket: index + 1, ...compareTicket(item.front || [], item.back || [], draw) }));
  const best = details.reduce((current, item) => {
    if (!current) return item;
    const currentScore = current.front_hits + current.back_hits;
    const itemScore = item.front_hits + item.back_hits;
    return itemScore > currentScore ? item : current;
  }, null);
  const hitTickets = details.filter((item) => item.prize_label !== "未命中固定奖级").length;
  return {
    actual: { issue: draw.issue, date: draw.date, front: draw.front, back: draw.back },
    mode: plan.mode,
    cost: plan.cost || 0,
    tickets: plan.tickets || details.length,
    best,
    details: details.slice(0, 20),
    hit_tickets: hitTickets,
    hit_rate: Math.round((hitTickets / Math.max(1, plan.tickets || details.length)) * 10000) / 100,
  };
}

export function getDemoReview() {
  const records = JSON.parse(localStorage.getItem("ceway_demo_records") || "[]");
  const fallback = records.length > 0 ? records : [
    {
      id: "demo-review-sample",
      saved_at: new Date().toISOString(),
      budget: 20,
      strategy: "balanced",
      latest_issue: "2025029",
      plan: buildDantuoPlan(20, "balanced", scoreFront(buildTrends(30)), scoreBack(buildTrends(30))),
    },
  ];
  const items = fallback.map((record) => {
    const draw = nextDemoDraw(record.latest_issue);
    if (!draw) {
      return {
        record_id: record.id,
        saved_at: record.saved_at,
        latest_issue: record.latest_issue,
        status: "pending",
        message: "推荐期之后暂无下一期开奖数据，暂不能复盘。",
      };
    }
    return {
      record_id: record.id,
      saved_at: record.saved_at,
      latest_issue: record.latest_issue,
      strategy: record.strategy,
      budget: record.budget,
      status: "reviewed",
      ...reviewDemoPlan(record.plan, draw),
    };
  });
  const reviewed = items.filter((item) => item.status === "reviewed");
  const hitRecords = reviewed.filter((item) => item.hit_tickets > 0);
  const bestItem = reviewed[0];
  return Promise.resolve({
    summary: {
      records: items.length,
      reviewed: reviewed.length,
      pending: items.length - reviewed.length,
      total_cost: reviewed.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hitRecords.length,
      record_hit_rate: Math.round((hitRecords.length / Math.max(1, reviewed.length)) * 10000) / 100,
      best_hit: bestItem?.best?.hit_label || "-",
      best_prize_label: bestItem?.best?.prize_label || "-",
    },
    items,
    disclaimer: "复盘只统计历史推荐与实际开奖号码的匹配结果，不代表未来命中概率或收益能力。",
  });
}

export function getDemoBacktest({ budget = 20, strategy = "balanced", periods = 12, window = 30 } = {}) {
  const count = Math.min(periods, HISTORY.length - 2);
  const start = Math.max(1, HISTORY.length - count - 1);
  const items = [];
  const baselineItems = [];

  for (let index = start; index < HISTORY.length - 1; index += 1) {
    const training = HISTORY.slice(0, index + 1);
    const trends = buildTrends(Math.min(window, training.length), training);
    const scores = scoreFront(trends);
    const backs = scoreBack(trends);
    const plan = strategy === "conservative"
      ? buildSinglePlan(budget, strategy, scores, backs)
      : buildDantuoPlan(budget, strategy, scores, backs);
    const actual = HISTORY[index + 1];
    items.push({
      source_issue: HISTORY[index].issue,
      actual_issue: actual.issue,
      actual_date: actual.date,
      strategy,
      budget,
      ...reviewDemoPlan(plan, actual),
    });

    const randomFront = [1 + (index % 31), 3 + (index % 28), 7 + (index % 24), 12 + (index % 20), 18 + (index % 16)]
      .map((number) => ((number - 1) % 35) + 1);
    const randomBack = [((index + 2) % 12) + 1, ((index + 8) % 12) + 1];
    const randomPlan = {
      mode: "single",
      cost: budget,
      tickets: Math.max(1, Math.floor(budget / 2)),
      items: [{ front: [...new Set(randomFront)].slice(0, 5).sort((a, b) => a - b), back: [...new Set(randomBack)].slice(0, 2).sort((a, b) => a - b) }],
    };
    baselineItems.push({
      source_issue: HISTORY[index].issue,
      actual_issue: actual.issue,
      actual_date: actual.date,
      strategy: "random",
      budget,
      ...reviewDemoPlan(randomPlan, actual),
    });
  }

  const summarize = (rows) => {
    const hitRows = rows.filter((item) => item.hit_tickets > 0);
    const best = rows.reduce((current, item) => {
      if (!current) return item;
      const currentScore = (current.best?.front_hits || 0) + (current.best?.back_hits || 0);
      const itemScore = (item.best?.front_hits || 0) + (item.best?.back_hits || 0);
      return itemScore > currentScore ? item : current;
    }, null);
    return {
      periods: rows.length,
      total_cost: rows.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hitRows.length,
      record_hit_rate: Math.round((hitRows.length / Math.max(1, rows.length)) * 10000) / 100,
      best_hit: best?.best?.hit_label || "-",
      best_prize_label: best?.best?.prize_label || "-",
      avg_front_hits: Math.round((rows.reduce((sum, item) => sum + (item.best?.front_hits || 0), 0) / Math.max(1, rows.length)) * 100) / 100,
      avg_back_hits: Math.round((rows.reduce((sum, item) => sum + (item.best?.back_hits || 0), 0) / Math.max(1, rows.length)) * 100) / 100,
    };
  };

  const summary = summarize(items);
  const baseline = summarize(baselineItems);
  summary.edge_vs_random = Math.round((summary.record_hit_rate - baseline.record_hit_rate) * 100) / 100;

  return Promise.resolve({
    config: {
      budget,
      strategy,
      periods: items.length,
      window,
      start_issue: items[0]?.source_issue || "-",
      end_issue: items.at(-1)?.actual_issue || "-",
    },
    summary,
    baseline,
    items: items.slice(-10).reverse(),
    baseline_items: baselineItems.slice(-10).reverse(),
    disclaimer: "演示环境使用样例数据回测，仅展示模块形态；本地环境使用 SQLite 全量数据。",
  });
}

function choose(items, count) {
  if (count === 0) return [[]];
  if (items.length < count) return [];
  const output = [];
  items.forEach((item, index) => {
    choose(items.slice(index + 1), count - 1).forEach((tail) => output.push([item, ...tail]));
  });
  return output;
}

function ssqPrizeLabel(frontHits, backHits) {
  if (frontHits === 6 && backHits === 1) return "一等奖";
  if (frontHits === 6) return "二等奖";
  if (frontHits === 5 && backHits === 1) return "三等奖";
  if ((frontHits === 5 && backHits === 0) || (frontHits === 4 && backHits === 1)) return "四等奖";
  if ((frontHits === 4 && backHits === 0) || (frontHits === 3 && backHits === 1)) return "五等奖";
  if (backHits === 1) return "六等奖";
  return "未命中固定奖级";
}

function compareSsqTicket(front, back, draw) {
  const frontHits = front.filter((number) => draw.front.includes(number)).length;
  const backHits = back.filter((number) => draw.back.includes(number)).length;
  return {
    front,
    back,
    front_hits: frontHits,
    back_hits: backHits,
    hit_label: `${frontHits}+${backHits}`,
    prize_label: ssqPrizeLabel(frontHits, backHits),
  };
}

function reviewDemoSsqPlan(plan, draw) {
  const details = plan.mode === "dantuo"
    ? choose(plan.front_tuo || [], 6 - (plan.front_dan || []).length).flatMap((tuo) =>
      (plan.back || []).map((back) => compareSsqTicket([...(plan.front_dan || []), ...tuo], [back], draw)))
    : (plan.items || []).map((item) => compareSsqTicket(item.front || [], item.back || [], draw));
  const best = details.reduce((current, item) => {
    if (!current) return item;
    return item.front_hits * 2 + item.back_hits > current.front_hits * 2 + current.back_hits ? item : current;
  }, null);
  const hitTickets = details.filter((item) => item.prize_label !== "未命中固定奖级").length;
  return {
    actual: { issue: draw.issue, date: draw.date, front: draw.front, back: draw.back },
    mode: plan.mode,
    cost: plan.cost || 0,
    tickets: plan.tickets || details.length,
    best,
    details: details.slice(0, 20),
    hit_tickets: hitTickets,
    hit_rate: Math.round((hitTickets / Math.max(1, plan.tickets || details.length)) * 10000) / 100,
  };
}

function nextDemoSsqDraw(issue) {
  if (!issue) return SSQ_HISTORY.at(-1);
  const index = SSQ_HISTORY.findIndex((row) => row.issue === issue);
  return index >= 0 && index + 1 < SSQ_HISTORY.length ? SSQ_HISTORY[index + 1] : null;
}

export function getDemoSsqReview() {
  const records = JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]");
  const items = records.map((record) => {
    const draw = nextDemoSsqDraw(record.latest_issue);
    if (!draw) {
      return {
        record_id: record.id,
        saved_at: record.saved_at,
        latest_issue: record.latest_issue,
        recommended_issue: record.plan?.recommended_issue,
        status: "pending",
        status_label: "待开奖",
        next_step: `等待第 ${record.plan?.recommended_issue || "下一"} 期开奖后复盘。`,
      };
    }
    return {
      record_id: record.id,
      saved_at: record.saved_at,
      latest_issue: record.latest_issue,
      strategy: record.strategy,
      budget: record.budget,
      status: "reviewed",
      status_label: "已复盘",
      ...reviewDemoSsqPlan(record.plan, draw),
    };
  });
  const reviewed = items.filter((item) => item.status === "reviewed");
  const hitRecords = reviewed.filter((item) => item.hit_tickets > 0);
  const best = reviewed.reduce((current, item) => {
    if (!current) return item;
    return (item.best?.front_hits || 0) > (current.best?.front_hits || 0) ? item : current;
  }, null);
  return Promise.resolve({
    summary: {
      records: items.length,
      reviewed: reviewed.length,
      pending: items.length - reviewed.length,
      total_cost: reviewed.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hitRecords.length,
      record_hit_rate: Math.round((hitRecords.length / Math.max(1, reviewed.length)) * 10000) / 100,
      best_hit: best?.best?.hit_label || "-",
      best_prize_label: best?.best?.prize_label || "-",
    },
    items,
    disclaimer: "复盘只统计保存方案与实际开奖号码的历史匹配，不代表未来收益。",
  });
}

export function getDemoSsqBacktest({ budget = 20, strategy = "balanced", periods = 12, window = 30 } = {}) {
  const count = Math.min(periods, SSQ_HISTORY.length - 31);
  const start = Math.max(30, SSQ_HISTORY.length - count - 1);
  const rows = [];
  const baselineRows = [];
  for (let index = start; index < SSQ_HISTORY.length - 1; index += 1) {
    const training = SSQ_HISTORY.slice(0, index + 1);
    const trends = buildSsqTrends(Math.min(window, training.length), training);
    const scores = scoreSsqFront(trends);
    const backs = scoreBack(trends);
    const plan = strategy === "conservative"
      ? buildSsqSinglePlan(budget, strategy, scores, backs)
      : buildSsqDantuoPlan(budget, strategy, scores, backs);
    const actual = SSQ_HISTORY[index + 1];
    rows.push({ source_issue: SSQ_HISTORY[index].issue, actual_issue: actual.issue, actual_date: actual.date, ...reviewDemoSsqPlan(plan, actual) });
    const randomFront = Array.from({ length: 6 }, (_, offset) => ((index * 7 + offset * 5) % 33) + 1);
    const randomPlan = {
      mode: "single",
      cost: 2,
      tickets: 1,
      items: [{ front: [...new Set(randomFront)].slice(0, 6).sort((a, b) => a - b), back: [((index * 3) % 16) + 1] }],
    };
    baselineRows.push(reviewDemoSsqPlan(randomPlan, actual));
  }
  const summarize = (items) => {
    const hits = items.filter((item) => item.hit_tickets > 0);
    const best = items.reduce((current, item) => !current || (item.best?.front_hits || 0) > (current.best?.front_hits || 0) ? item : current, null);
    return {
      periods: items.length,
      total_cost: items.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hits.length,
      record_hit_rate: Math.round((hits.length / Math.max(1, items.length)) * 10000) / 100,
      best_hit: best?.best?.hit_label || "-",
      best_prize_label: best?.best?.prize_label || "-",
      avg_front_hits: Math.round((items.reduce((sum, item) => sum + (item.best?.front_hits || 0), 0) / Math.max(1, items.length)) * 100) / 100,
      avg_back_hits: Math.round((items.reduce((sum, item) => sum + (item.best?.back_hits || 0), 0) / Math.max(1, items.length)) * 100) / 100,
    };
  };
  const summary = summarize(rows);
  const baseline = summarize(baselineRows);
  summary.edge_vs_random = Math.round((summary.record_hit_rate - baseline.record_hit_rate) * 100) / 100;
  return Promise.resolve({
    config: { budget, strategy, periods: rows.length, window, start_issue: rows[0]?.source_issue || "-", end_issue: rows.at(-1)?.actual_issue || "-" },
    summary,
    baseline,
    items: rows.slice(-10).reverse(),
    disclaimer: "静态快照回测只验证流程和历史匹配，不预测未来。",
  });
}

export function getDemoSsqDraws(limit = 10) {
  return Promise.resolve(SSQ_HISTORY.slice(-limit).reverse());
}

export function getDemoSsqStatus() {
  const latest = SSQ_HISTORY.at(-1);
  return Promise.resolve({
    storage: "static_demo",
    path: "内置 SSQ CSV 快照",
    draw_count: SSQ_HISTORY.length,
    record_count: JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]").length,
    review_count: 0,
    first_issue: SSQ_HISTORY[0]?.issue,
    first_date: SSQ_HISTORY[0]?.date,
    latest_issue: latest?.issue,
    latest_date: latest?.date,
    quality: { level: "snapshot", label: "静态快照", message: "静态演示数据更新至当前发布版本。", missing_count: 0, missing_issues: [] },
    last_sync: null,
  });
}

export function getDemoDraws(limit = 10) {
  return Promise.resolve(
    HISTORY.slice(-limit).reverse().map((row) => ({
      issue: row.issue,
      date: row.date,
      front: row.front,
      back: row.back,
    })),
  );
}

export function getDemoDltStatus() {
  const latest = HISTORY.at(-1);
  return Promise.resolve({
    storage: "static_demo",
    path: "内置 DLT CSV 快照",
    draw_count: HISTORY.length,
    record_count: JSON.parse(localStorage.getItem("ceway_demo_records") || "[]").length,
    review_count: 0,
    first_issue: HISTORY[0]?.issue,
    first_date: HISTORY[0]?.date,
    latest_issue: latest?.issue,
    latest_date: latest?.date,
    quality: { level: "snapshot", label: "静态快照", message: "静态演示数据更新至当前发布版本。", missing_count: 0, missing_issues: [] },
    last_sync: null,
  });
}
