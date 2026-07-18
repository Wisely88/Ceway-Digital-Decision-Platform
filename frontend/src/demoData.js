import dltHistoryCsv from "../../backend/data/dlt_history.csv?raw";
import ssqHistoryCsv from "../../backend/data/ssq_history.csv?raw";
import dltPrizeUrl from "../../backend/data/dlt_prizes.json?url";
import ssqPrizeUrl from "../../backend/data/ssq_prizes.json?url";
import { buildBehaviorProfile } from "./behavior";

const prizeCache = new Map();

async function loadPrizeIssues(url) {
  if (!prizeCache.has(url)) {
    prizeCache.set(url, fetch(url).then((response) => {
      if (!response.ok) throw new Error(`奖金快照加载失败：${response.status}`);
      return response.json();
    }).then((payload) => payload.issues || {}));
  }
  return prizeCache.get(url);
}

async function loadPrizeSnapshot(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`奖金快照加载失败：${response.status}`);
  return response.json();
}

function prizeFinancials(distribution, issueData, cost, appended = false, multiplier = 1) {
  const prizes = issueData?.prizes || {};
  const additionalPrizes = issueData?.additional_prizes || {};
  let prizeAmount = 0;
  const safeMultiplier = Math.max(1, Math.min(99, Math.floor(Number(multiplier || 1))));
  const missing = [];
  Object.entries(distribution || {}).forEach(([label, count]) => {
    if (typeof prizes[label] !== "number") missing.push(label);
    else {
      prizeAmount += prizes[label] * count * safeMultiplier;
      if (appended) {
        if (typeof additionalPrizes[label] !== "number") missing.push(`${label}(追加)`);
        else prizeAmount += additionalPrizes[label] * count * safeMultiplier;
      }
    }
  });
  const complete = missing.length === 0;
  const netProfit = complete ? prizeAmount - Number(cost || 0) : null;
  return {
    prize_amount: prizeAmount,
    prize_amount_complete: complete,
    missing_prize_labels: missing,
    net_profit: netProfit,
    roi: complete && cost ? Math.round((netProfit / cost) * 10000) / 100 : null,
    prize_source: issueData?.source || "",
  };
}

function reviewFinancialSummary(items) {
  const reviewed = items.filter((item) => item.status === "reviewed");
  const totalCost = reviewed.reduce((sum, item) => sum + Number(item.cost || 0), 0);
  const totalPrize = reviewed.reduce((sum, item) => sum + Number(item.prize_amount || 0), 0);
  const complete = reviewed.every((item) => item.prize_amount_complete);
  const netProfit = complete ? totalPrize - totalCost : null;
  return {
    total_prize: totalPrize,
    net_profit: netProfit,
    roi: complete && totalCost ? Math.round((netProfit / totalCost) * 10000) / 100 : null,
    roi_complete: complete,
  };
}

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
const HISTORY = PARSED_DLT_HISTORY;

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
  const backLastSeen = new Map();
  history.forEach((row, index) => row.back.forEach((number) => backLastSeen.set(number, index)));
  const omissions = Array.from({ length: 35 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    return { number, missing: seenAt === undefined ? history.length : history.length - seenAt - 1 };
  });
  const lastSeenRows = Array.from({ length: 35 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    const row = seenAt === undefined ? null : history[seenAt];
    return { number, issue: row?.issue || null, date: row?.date || null };
  });
  const backOmissions = Array.from({ length: 12 }, (_, index) => {
    const number = index + 1;
    const seenAt = backLastSeen.get(number);
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
    last_seen: lastSeenRows,
    back_omissions: backOmissions,
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
  const lastSeenByNumber = new Map((trends.last_seen || []).map((item) => [item.number, item]));
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
      last_seen_issue: lastSeenByNumber.get(number)?.issue || null,
      last_seen_date: lastSeenByNumber.get(number)?.date || null,
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
  const heatByNumber = new Map(trends.hot_back.map((item) => [item.number, item.count]));
  const missingByNumber = new Map((trends.back_omissions || []).map((item) => [item.number, item.missing]));
  const maxHeat = Math.max(...heatByNumber.values());
  const maxMissing = Math.max(...missingByNumber.values(), 0);
  const maxNumber = Math.max(...heatByNumber.keys());
  const midpoint = Math.floor(maxNumber / 2);
  const oddTotal = [...heatByNumber].filter(([number]) => number % 2 === 1).reduce((sum, [, count]) => sum + count, 0);
  const evenTotal = [...heatByNumber].filter(([number]) => number % 2 === 0).reduce((sum, [, count]) => sum + count, 0);
  const smallTotal = [...heatByNumber].filter(([number]) => number <= midpoint).reduce((sum, [, count]) => sum + count, 0);
  const largeTotal = [...heatByNumber].filter(([number]) => number > midpoint).reduce((sum, [, count]) => sum + count, 0);

  return [...heatByNumber.keys()].map((number) => {
    const heat = normalize(heatByNumber.get(number) || 0, maxHeat);
    const missing = normalize(missingByNumber.get(number) || 0, maxMissing);
    const parityScore = (number % 2 === 1 ? oddTotal <= evenTotal : evenTotal <= oddTotal) ? 100 : 85;
    const sizeScore = (number <= midpoint ? smallTotal <= largeTotal : largeTotal <= smallTotal) ? 100 : 85;
    const balanced = (parityScore + sizeScore) / 2;
    const total = Math.round((heat * 0.4 + missing * 0.3 + balanced * 0.3) * 100) / 100;
    return {
      number,
      heat_count: heatByNumber.get(number) || 0,
      missing_periods: missingByNumber.get(number) || 0,
      heat_score: heat,
      missing_score: missing,
      balance_score: balanced,
      total_score: total,
      score: total,
      explanation: `热度${heat}分、遗漏${missing}分、历史结构平衡${balanced}分；综合评分 ${total}。`,
    };
  }).sort((left, right) => right.total_score - left.total_score || left.number - right.number)
    .map((row, index) => ({ ...row, rank: index + 1 }));
}

function buildSsqTrends(window = 100, history = SSQ_HISTORY) {
  const recent = history.slice(-window);
  const frontCounts = countValues(recent.flatMap((row) => row.front), 1, 33);
  const backCounts = countValues(recent.flatMap((row) => row.back), 1, 16);
  const lastSeen = new Map();
  history.forEach((row, index) => row.front.forEach((number) => lastSeen.set(number, index)));
  const backLastSeen = new Map();
  history.forEach((row, index) => row.back.forEach((number) => backLastSeen.set(number, index)));
  const omissions = Array.from({ length: 33 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    return { number, missing: seenAt === undefined ? history.length : history.length - seenAt - 1 };
  });
  const lastSeenRows = Array.from({ length: 33 }, (_, index) => {
    const number = index + 1;
    const seenAt = lastSeen.get(number);
    const row = seenAt === undefined ? null : history[seenAt];
    return { number, issue: row?.issue || null, date: row?.date || null };
  });
  const backOmissions = Array.from({ length: 16 }, (_, index) => {
    const number = index + 1;
    const seenAt = backLastSeen.get(number);
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
    last_seen: lastSeenRows,
    back_omissions: backOmissions,
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
  const lastSeenByNumber = new Map((trends.last_seen || []).map((item) => [item.number, item]));
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
      last_seen_issue: lastSeenByNumber.get(number)?.issue || null,
      last_seen_date: lastSeenByNumber.get(number)?.date || null,
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

function selectSeparatedBack(rankedBack, count, excluded = []) {
  const excludedSet = new Set(excluded);
  let pool = rankedBack.filter((number) => !excludedSet.has(number));
  if (pool.length < count) pool = rankedBack;
  const band = pool.slice(0, Math.min(pool.length, count + 6));
  const candidates = choose(band, count);
  const separated = candidates.filter((numbers) => {
    const ordered = [...numbers].sort((left, right) => left - right);
    return !ordered.some((number, index) => index > 0 && number - ordered[index - 1] === 1);
  });
  return [...(separated[0] || candidates[0] || pool.slice(0, count))].sort((left, right) => left - right);
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
    const back = selectSeparatedBack(backPool, 2, front);
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
  const back = selectSeparatedBack(rankedBack, structure.backCount, frontDan);
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
    product: { name: "策维", english_name: "Ceway", subtitle: "Digital Decision Platform", framework: "Powered by CBGO Framework", version: "v1.12 Stable" },
    disclaimer: "策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
    history_count: HISTORY.length,
    latest_issue: latest.issue,
    recommended_issue: recommendedIssue,
    data_status: {
      source: "published_snapshot",
      source_label: "完整历史快照",
      path: "DLT 历史开奖 CSV",
      latest_issue: latest.issue,
      latest_date: latest.date,
      is_sample: false,
      message: `当前分析基于发布时校验的 ${HISTORY.length} 期大乐透历史开奖数据。`,
    },
    top_numbers: scoreTable.slice(0, 5).map((row) => row.number),
    budget: Number(budget),
    strategy,
    window: trends.window,
    recommended_amount: Math.max(...plans.map((plan) => plan.cost)),
    capital_state: buildCapital(lastPrize, Number(principal), balance, levelUnits),
    trends,
    score_table: scoreTable,
    back_scoreboard: backScores,
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
    product: { name: "策维", english_name: "Ceway", subtitle: "Digital Decision Platform", framework: "Powered by CBGO Framework", version: "v1.12 Stable" },
    disclaimer: "策维不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。",
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
      storage: "published_snapshot",
      source_label: "完整历史快照",
      path: "SSQ 历史开奖 CSV",
      draw_count: SSQ_HISTORY.length,
      latest_issue: latest.issue,
      latest_date: latest.date,
      quality: { level: "snapshot", label: "连续完整", message: `已打包 ${SSQ_HISTORY.length} 期双色球历史记录，数据随网站发布版本更新。`, missing_count: 0, missing_issues: [] },
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

export async function getDemoBehavior(scene) {
  const isSsq = String(scene).toUpperCase() === "SSQ";
  const records = isSsq ? await getDemoSsqRecords() : await getDemoRecords();
  const review = isSsq ? await getDemoSsqReview() : await getDemoReview();
  const snapshot = await loadPrizeSnapshot(isSsq ? ssqPrizeUrl : dltPrizeUrl);
  return buildBehaviorProfile(records, review, snapshot);
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

function prizeLabel(frontHits, backHits, issue) {
  const newRules = Number(issue || 0) >= 26014;
  if (frontHits === 5 && backHits === 2) return "一等奖";
  if (frontHits === 5 && backHits === 1) return "二等奖";
  if (newRules) {
    if (frontHits === 5 || (frontHits === 4 && backHits === 2)) return "三等奖";
    if (frontHits === 4 && backHits === 1) return "四等奖";
    if (frontHits === 4 || (frontHits === 3 && backHits === 2)) return "五等奖";
    if ((frontHits === 3 && backHits === 1) || (frontHits === 2 && backHits === 2)) return "六等奖";
    if ((frontHits === 3 && backHits === 0) || (frontHits === 2 && backHits === 1) || (frontHits <= 1 && backHits === 2)) return "七等奖";
    return "未命中固定奖级";
  }
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
    prize_label: prizeLabel(frontHits, backHits, draw.issue),
  };
}

function nextDemoDraw(issue) {
  if (!issue) return HISTORY[HISTORY.length - 1];
  const index = HISTORY.findIndex((row) => row.issue === issue);
  return index >= 0 && index + 1 < HISTORY.length ? HISTORY[index + 1] : null;
}

function reviewDemoPlan(plan, draw, prizeIssues = {}) {
  const details = plan.mode === "dantuo"
    ? choose(plan.front_tuo || [], 5 - (plan.front_dan || []).length).flatMap((tuo) =>
      choose(plan.back || [], 2).map((back) => compareTicket([...(plan.front_dan || []), ...tuo], back, draw)))
    : (plan.items || []).map((item, index) => ({ ticket: index + 1, ...compareTicket(item.front || [], item.back || [], draw) }));
  const best = details.reduce((current, item) => {
    if (!current) return item;
    const currentScore = current.front_hits + current.back_hits;
    const itemScore = item.front_hits + item.back_hits;
    return itemScore > currentScore ? item : current;
  }, null);
  const hitTickets = details.filter((item) => item.prize_label !== "未命中固定奖级").length;
  const prizeDistribution = details.reduce((distribution, item) => {
    if (item.prize_label !== "未命中固定奖级") {
      distribution[item.prize_label] = (distribution[item.prize_label] || 0) + 1;
    }
    return distribution;
  }, {});
  const result = {
    actual: { issue: draw.issue, date: draw.date, front: draw.front, back: draw.back },
    mode: plan.mode,
    cost: plan.cost || 0,
    tickets: plan.tickets || details.length,
    best,
    details: details.slice(0, 20),
    hit_tickets: hitTickets,
    hit_rate: Math.round((hitTickets / Math.max(1, plan.tickets || details.length)) * 10000) / 100,
    prize_distribution: prizeDistribution,
  };
  return { ...result, ...prizeFinancials(prizeDistribution, prizeIssues[draw.issue], result.cost, Boolean(plan.appended), plan.multiplier) };
}

export async function getDemoReview() {
  const prizeIssues = await loadPrizeIssues(dltPrizeUrl);
  const records = JSON.parse(localStorage.getItem("ceway_demo_records") || "[]");
  const items = records.map((record) => {
    const draw = nextDemoDraw(record.latest_issue);
    if (!draw) {
      return {
        record_id: record.id,
        saved_at: record.saved_at,
        latest_issue: record.latest_issue,
        recommended_issue: record.plan?.recommended_issue,
        plan: record.plan,
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
      plan: record.plan,
      status: "reviewed",
      ...reviewDemoPlan(record.plan, draw, prizeIssues),
    };
  });
  const reviewed = items.filter((item) => item.status === "reviewed");
  const hitRecords = reviewed.filter((item) => item.hit_tickets > 0);
  const bestItem = reviewed[0];
  return {
    summary: {
      records: items.length,
      reviewed: reviewed.length,
      pending: items.length - reviewed.length,
      total_cost: reviewed.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hitRecords.length,
      record_hit_rate: Math.round((hitRecords.length / Math.max(1, reviewed.length)) * 10000) / 100,
      best_hit: bestItem?.best?.hit_label || "-",
      best_prize_label: bestItem?.best?.prize_label || "-",
      ...reviewFinancialSummary(items),
    },
    items,
    disclaimer: "复盘只统计历史推荐与实际开奖号码的匹配结果，不代表未来命中概率或收益能力。",
  };
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

function reviewDemoSsqPlan(plan, draw, prizeIssues = {}) {
  const details = plan.mode === "dantuo"
    ? choose(plan.front_tuo || [], 6 - (plan.front_dan || []).length).flatMap((tuo) =>
      (plan.back || []).map((back) => compareSsqTicket([...(plan.front_dan || []), ...tuo], [back], draw)))
    : (plan.items || []).map((item) => compareSsqTicket(item.front || [], item.back || [], draw));
  const best = details.reduce((current, item) => {
    if (!current) return item;
    return item.front_hits * 2 + item.back_hits > current.front_hits * 2 + current.back_hits ? item : current;
  }, null);
  const hitTickets = details.filter((item) => item.prize_label !== "未命中固定奖级").length;
  const prizeDistribution = details.reduce((distribution, item) => {
    if (item.prize_label !== "未命中固定奖级") {
      distribution[item.prize_label] = (distribution[item.prize_label] || 0) + 1;
    }
    return distribution;
  }, {});
  const result = {
    actual: { issue: draw.issue, date: draw.date, front: draw.front, back: draw.back },
    mode: plan.mode,
    cost: plan.cost || 0,
    tickets: plan.tickets || details.length,
    best,
    details: details.slice(0, 20),
    hit_tickets: hitTickets,
    hit_rate: Math.round((hitTickets / Math.max(1, plan.tickets || details.length)) * 10000) / 100,
    prize_distribution: prizeDistribution,
  };
  return { ...result, ...prizeFinancials(prizeDistribution, prizeIssues[draw.issue], result.cost, false, plan.multiplier) };
}

function nextDemoSsqDraw(issue) {
  if (!issue) return SSQ_HISTORY.at(-1);
  const index = SSQ_HISTORY.findIndex((row) => row.issue === issue);
  return index >= 0 && index + 1 < SSQ_HISTORY.length ? SSQ_HISTORY[index + 1] : null;
}

export async function getDemoSsqReview() {
  const prizeIssues = await loadPrizeIssues(ssqPrizeUrl);
  const records = JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]");
  const items = records.map((record) => {
    const draw = nextDemoSsqDraw(record.latest_issue);
    if (!draw) {
      return {
        record_id: record.id,
        saved_at: record.saved_at,
        latest_issue: record.latest_issue,
        recommended_issue: record.plan?.recommended_issue,
        plan: record.plan,
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
      plan: record.plan,
      status: "reviewed",
      status_label: "已复盘",
      ...reviewDemoSsqPlan(record.plan, draw, prizeIssues),
    };
  });
  const reviewed = items.filter((item) => item.status === "reviewed");
  const hitRecords = reviewed.filter((item) => item.hit_tickets > 0);
  const best = reviewed.reduce((current, item) => {
    if (!current) return item;
    return (item.best?.front_hits || 0) > (current.best?.front_hits || 0) ? item : current;
  }, null);
  return {
    summary: {
      records: items.length,
      reviewed: reviewed.length,
      pending: items.length - reviewed.length,
      total_cost: reviewed.reduce((sum, item) => sum + item.cost, 0),
      hit_records: hitRecords.length,
      record_hit_rate: Math.round((hitRecords.length / Math.max(1, reviewed.length)) * 10000) / 100,
      best_hit: best?.best?.hit_label || "-",
      best_prize_label: best?.best?.prize_label || "-",
      ...reviewFinancialSummary(items),
    },
    items,
    disclaimer: "复盘只统计保存方案与实际开奖号码的历史匹配，不代表未来收益。",
  };
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

function paginateDraws(history, { limit = 12, offset = 0, issue = "" } = {}) {
  const normalizedIssue = String(issue || "").trim();
  const filtered = history
    .slice()
    .reverse()
    .filter((row) => !normalizedIssue || row.issue.includes(normalizedIssue));
  return {
    items: filtered.slice(offset, offset + limit),
    total: filtered.length,
    limit,
    offset,
    issue: normalizedIssue,
  };
}

export function searchDemoSsqDraws(params = {}) {
  return Promise.resolve(paginateDraws(SSQ_HISTORY, params));
}

export function getDemoSsqStatus() {
  const latest = SSQ_HISTORY.at(-1);
  return Promise.resolve({
    storage: "published_snapshot",
    path: "SSQ 历史开奖 CSV",
    draw_count: SSQ_HISTORY.length,
    record_count: JSON.parse(localStorage.getItem("ceway_demo_ssq_records") || "[]").length,
    review_count: 0,
    first_issue: SSQ_HISTORY[0]?.issue,
    first_date: SSQ_HISTORY[0]?.date,
    latest_issue: latest?.issue,
    latest_date: latest?.date,
    quality: { level: "snapshot", label: "连续完整", message: `已打包 ${SSQ_HISTORY.length} 期双色球历史记录，数据随网站发布版本更新。`, missing_count: 0, missing_issues: [] },
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

export function searchDemoDltDraws(params = {}) {
  return Promise.resolve(paginateDraws(HISTORY, params));
}

export function getDemoDltStatus() {
  const latest = HISTORY.at(-1);
  return Promise.resolve({
    storage: "published_snapshot",
    path: "DLT 历史开奖 CSV",
    draw_count: HISTORY.length,
    record_count: JSON.parse(localStorage.getItem("ceway_demo_records") || "[]").length,
    review_count: 0,
    first_issue: HISTORY[0]?.issue,
    first_date: HISTORY[0]?.date,
    latest_issue: latest?.issue,
    latest_date: latest?.date,
    quality: { level: "snapshot", label: "连续完整", message: `已打包 ${HISTORY.length} 期大乐透历史记录，数据随网站发布版本更新。`, missing_count: 0, missing_issues: [] },
    last_sync: null,
  });
}
