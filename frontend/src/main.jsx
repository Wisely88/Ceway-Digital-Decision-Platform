import React, { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  CircleCheck,
  Clipboard,
  Coins,
  Database,
  ArrowLeft,
  GitCompare,
  FileStack,
  FileUp,
  Gauge,
  History,
  Home,
  Play,
  RefreshCw,
  Save,
  Settings,
  ShieldAlert,
  Sparkles,
  Table2,
  TrendingUp,
  WalletCards,
} from "lucide-react";
import {
  deleteDltRecord,
  deleteSsqRecord,
  getDltBacktest,
  getDltDashboard,
  getDltDataStatus,
  getDltDraws,
  getDltRecords,
  getDltReview,
  getScenes,
  getSsqBacktest,
  getSsqDashboard,
  getSsqDataStatus,
  getSsqDraws,
  getSsqRecords,
  getSsqReview,
  importDltHistory,
  importSsqHistory,
  saveDltRecord,
  saveSsqRecord,
  searchDltDraws,
  searchSsqDraws,
  syncDltHistory,
  syncSsqHistory,
} from "./api";
import { buildDecisionBrief, cumulativeSpending, recentSpending } from "./decision";
import { evaluatePackage, packageCatalog, PACKAGE_SOURCES } from "./packageEvaluator";
import { selectScoredCombination } from "./suggestionRotation";
import { decodeSyncBundle, encodeSyncBundle } from "./syncCodec";
import "./styles.css";

const BUILD_TIME = typeof __CEWAY_BUILD_TIME__ === "string" ? __CEWAY_BUILD_TIME__ : "";
const TrendBarChartView = lazy(() => import("./Charts").then((module) => ({ default: module.TrendBarChart })));
const TrendLineChartView = lazy(() => import("./Charts").then((module) => ({ default: module.TrendLineChart })));
const CapitalSpendChartView = lazy(() => import("./Charts").then((module) => ({ default: module.CapitalSpendChart })));

function ChartFallback({ height = 250 }) {
  return <div className="chart-loading" style={{ minHeight: height }}>正在加载图表...</div>;
}

function Badge({ children, tone = "default" }) {
  return <span className={`badge badge-${tone}`}>{children}</span>;
}

function StatCard({ icon: Icon, label, value, meta }) {
  return (
    <section className="stat-card">
      <div className="stat-icon">
        <Icon size={18} />
      </div>
      <div>
        <p>{label}</p>
        <strong>{value}</strong>
        {meta && <span>{meta}</span>}
      </div>
    </section>
  );
}

function TopNumbersCard({ rows }) {
  const [expanded, setExpanded] = useState(false);
  const displayRows = expanded ? rows.slice(0, 20) : rows.slice(0, 5);
  const value = displayRows.map((row) => String(row.number).padStart(2, "0")).join(" ");

  return (
    <button className={`stat-card stat-card-button ${expanded ? "expanded" : ""}`} onClick={() => setExpanded(!expanded)} type="button">
      <div className="stat-icon">
        <Sparkles size={18} />
      </div>
      <div>
        <p>{expanded ? "Top20号码" : "Top号码"}</p>
        <strong>{value}</strong>
        <span>{expanded ? "点击收起" : "点击展开 Top20"}</span>
      </div>
    </button>
  );
}

function NumberBall({ children, tone = "front" }) {
  return <span className={`number-ball ${tone}`}>{children}</span>;
}

function SceneLogo({ code }) {
  return (
    <div className={`scene-logo ${code.toLowerCase()}`}>
      {code === "DLT" && (
        <>
          <span>DLT</span>
          <i>35</i>
          <b>12</b>
        </>
      )}
      {code === "SSQ" && (
        <>
          <span>SSQ</span>
          <i>33</i>
          <b>16</b>
        </>
      )}
      {code === "K8" && (
        <>
          <span>K8</span>
          <i>80</i>
          <b>20</b>
        </>
      )}
      {code === "CUSTOM" && (
        <>
          <Settings size={30} />
          <span>CUSTOM</span>
        </>
      )}
    </div>
  );
}

const PRODUCT_STATUS = [
  {
    label: "产品版本",
    value: "Ceway MVP",
    detail: "Digital Decision Platform",
    tone: "blue",
  },
  {
    label: "当前版本",
    value: "V1.8 验证闭环版",
    detail: "多方案比较、实际奖金、跨设备同步与按需加载",
    tone: "green",
  },
  {
    label: "核心原则",
    value: "看清随机性",
    detail: "不预测、不追投、不用历史结果承诺未来",
    tone: "purple",
  },
  {
    label: "更新日志",
    value: "DLT + SSQ",
    detail: "双场景核心链路已进入验收",
    tone: "orange",
  },
];

const ROADMAP_ITEMS = [
  {
    version: "V1.3",
    title: "Decision Pipeline",
    description: "历史开奖 -> 趋势计算 -> 号码评分 -> 预算约束 -> 组合生成 -> 决策解释 -> 投注方案。",
  },
  {
    version: "V1.4",
    title: "SQLite 数据增强版",
    description: "开奖管理、历史记录、推荐方案持久化和数据维护能力。",
  },
  {
    version: "V1.5",
    title: "回测验证版",
    description: "历史回测、随机选号对照组、覆盖统计和历史匹配表现。",
  },
  {
    version: "V1.6",
    title: "决策风控版",
    description: "支出解释、覆盖与倍率、资金暴露、周期上限、连续加码提醒和长期表现说明。",
  },
  {
    version: "V1.7",
    title: "套餐评估版",
    description: "按地区和活动有效性，评估套餐实付、票面展开注数、赠票覆盖与预算占用。",
  },
  {
    version: "V1.8",
    title: "验证闭环版",
    description: "多方案比较、号码明细、实际奖金与 ROI、同步码、数据来源和前端按需加载。",
  },
];

const STRATEGY_LABELS = {
  conservative: "保守",
  balanced: "均衡",
  aggressive: "激进",
  manual_workbench: "系统建议",
  manual_selection: "人工选号",
};

function planModeLabel(mode) {
  return mode === "dantuo" ? "胆拖" : "单式";
}

function lotteryLabels(source = {}) {
  return {
    front: "前区",
    back: "后区",
    front_hits: "前区命中",
    back_hits: "后区命中",
    ...(source.play_labels || {}),
  };
}

function classifyError(error, fallback = "操作失败") {
  const message = error?.message || String(error || fallback);
  if (/Failed to fetch|NetworkError|Load failed|Network request failed|ERR_NGROK|offline/i.test(message)) {
    return {
      title: "网络或网关异常",
      detail: "无法连接本地后端或公网网关。请确认本地服务、网关和 ngrok 隧道在线后重试。",
      layer: "网关",
    };
  }
  if (/API 4\d\d|422|validation|预算|CSV|参数|不符合/i.test(message)) {
    return { title: "输入或数据不符合规则", detail: message, layer: "输入" };
  }
  if (/API 5\d\d|Internal Server Error|Traceback/i.test(message)) {
    return { title: "后端服务异常", detail: message, layer: "后端" };
  }
  if (/clipboard|permission|not allowed|denied/i.test(message)) {
    return { title: "浏览器权限限制", detail: message, layer: "浏览器" };
  }
  return { title: fallback, detail: message, layer: "未知" };
}

function ErrorNotice({ error, onRetry }) {
  if (!error) return null;
  const info = classifyError(error);
  return (
    <section className="error-panel" role="alert">
      <div>
        <Badge>{info.layer}</Badge>
        <strong>{info.title}</strong>
        <p>{info.detail}</p>
      </div>
      {onRetry && (
        <button className="ghost-button compact" onClick={onRetry} type="button">
          <RefreshCw size={14} />
          重试
        </button>
      )}
    </section>
  );
}

function reviewStatusMap(review) {
  return new Map(
    (review?.items || []).map((item) => [
      item.record_id,
      {
        label: item.status_label || (item.status === "reviewed" ? "已复盘" : "待开奖"),
        nextStep: item.next_step || item.message || "",
      },
    ]),
  );
}

function formatNumber(number) {
  return String(number).padStart(2, "0");
}

function rangeNumbers(max) {
  return Array.from({ length: max }, (_, index) => index + 1);
}

function combinationCount(total, pick) {
  if (pick < 0 || pick > total) return 0;
  if (pick === 0 || pick === total) return 1;
  const safePick = Math.min(pick, total - pick);
  let result = 1;
  for (let index = 1; index <= safePick; index += 1) {
    result = (result * (total - safePick + index)) / index;
  }
  return Math.round(result);
}

function displayNumbers(numbers) {
  return [...numbers].sort((left, right) => left - right).map(formatNumber);
}

function planFrontNumbers(plan) {
  if (!plan) return [];
  if (plan.mode === "dantuo") return [...(plan.front_dan || []), ...(plan.front_tuo || [])];
  return [...new Set((plan.items || []).flatMap((item) => item.front || []))];
}

function planLabelsForScene(scene) {
  if (scene === "SSQ") {
    return {
      front: "红球",
      back: "蓝球",
      dan: "红球胆码",
      tuo: "红球拖码",
      single: "单式票",
      rule: "双色球红球 33 选 6，蓝球 16 选 1；方案仅用于流程管理和复盘。",
      front_hits: "红球命中",
      back_hits: "蓝球命中",
    };
  }
  return {
    front: "前区",
    back: "后区",
    dan: "前区胆码",
    tuo: "前区拖码",
    single: "单式票",
    rule: "大乐透前区 35 选 5，后区 12 选 2；方案仅用于流程管理和复盘。",
    front_hits: "前区命中",
    back_hits: "后区命中",
  };
}

function sceneRules(scene) {
  return scene === "SSQ"
    ? { scene: "SSQ", playName: "双色球", frontMax: 33, backMax: 16, frontPick: 6, backPick: 1 }
    : { scene: "DLT", playName: "大乐透", frontMax: 35, backMax: 12, frontPick: 5, backPick: 2 };
}

function buildSingleItems({ rules, frontRows, backRows, count, variant }) {
  const items = [];
  for (let index = 0; index < count; index += 1) {
    const front = selectScoredCombination(frontRows, rules.frontMax, rules.frontPick, variant + index);
    const back = selectScoredCombination(backRows, rules.backMax, rules.backPick, variant + index);
    items.push({
      front: [...front].sort((left, right) => left - right),
      back: [...back].sort((left, right) => left - right),
      front_display: displayNumbers(front),
      back_display: displayNumbers(back),
      explanation: ["按评分池顺位轮换生成，避免每组完全重复。"],
    });
  }
  return items;
}

function aiCommentaryForPlan(plan, labels) {
  if (plan.mode === "dantuo") {
    return [
      `${labels.dan}来自当前评分靠前号码，适合作为核心观察位。`,
      `${labels.tuo}用于扩展覆盖，预算越高可适当增加拖码数量。`,
      `${labels.back}按评分和分散度选择，保存后会进入待开奖复盘队列。`,
    ];
  }
  return [
    "单式方案更适合小预算，费用清晰、复盘直接。",
    "每注号码按评分池轮换生成，避免多组号码完全重叠。",
    "保存后可在推荐复盘中与下一期开奖做对比。",
  ];
}

function buildAiBettingPlan({ scene, scoreRows, backScoreRows, budget, mode, ticketCount, danCount, tuoCount, backCount, latestIssue, recommendedIssue, variant }) {
  const rules = sceneRules(scene);
  const labels = planLabelsForScene(scene);
  const backRows = backScoreRows?.length
    ? backScoreRows
    : rangeNumbers(rules.backMax).map((number) => ({ number, total_score: 0 }));
  const backScoreMap = new Map(backRows.map((row) => [Number(row.number), row]));

  if (mode === "single") {
    const affordable = Math.max(1, Math.floor(Number(budget || 0) / 2));
    const count = Math.max(1, Math.min(Number(ticketCount || 1), affordable));
    const items = buildSingleItems({ rules, frontRows: scoreRows, backRows, count, variant });
    return {
      scene,
      play_name: rules.playName,
      play_labels: labels,
      mode: "single",
      source: "rule_suggestion",
      strategy: "manual_workbench",
      based_on_issue: latestIssue,
      recommended_issue: recommendedIssue,
      recommendation_label: `基于第 ${latestIssue || "-"} 期开奖数据，生成第 ${recommendedIssue || "下一"} 期历史规则单式方案。`,
      cost: items.length * 2,
      tickets: items.length,
      items,
      reason: `按用户设置生成 ${items.length} 注单式，费用 ${items.length * 2} 元。`,
      explanation: aiCommentaryForPlan({ mode: "single" }, labels),
      score_basis: `${labels.front}和${labels.back}均先按热度0.4 + 遗漏0.3 + 历史结构平衡0.3评分，再从高分候选带生成变体。`,
      budget_analysis: {
        budget: Number(budget || 0),
        cost: items.length * 2,
        unused: Math.max(0, Number(budget || 0) - items.length * 2),
        utilization: Number(budget || 0) ? Math.round((items.length * 2 / Number(budget || 0)) * 10000) / 100 : 0,
        explanation: "按照手动填写注数生成；如预算不足，系统自动压缩到预算范围内。",
      },
    };
  }

  const safeDan = Math.max(1, Math.min(Number(danCount || 1), rules.frontPick - 1));
  const safeTuo = Math.max(rules.frontPick - safeDan, Number(tuoCount || rules.frontPick));
  const safeBack = Math.max(rules.backPick, Number(backCount || rules.backPick));
  const frontDan = selectScoredCombination(scoreRows, rules.frontMax, safeDan, variant)
    .sort((left, right) => left - right);
  const frontTuo = selectScoredCombination(scoreRows, rules.frontMax, safeTuo, variant, frontDan)
    .sort((left, right) => left - right);
  const back = selectScoredCombination(backRows, rules.backMax, safeBack, variant).sort((left, right) => left - right);
  const tickets = combinationCount(frontTuo.length, rules.frontPick - frontDan.length) * combinationCount(back.length, rules.backPick);
  const cost = tickets * 2;
  return {
    scene,
    play_name: rules.playName,
    play_labels: labels,
    mode: "dantuo",
    source: "rule_suggestion",
    strategy: "manual_workbench",
    based_on_issue: latestIssue,
    recommended_issue: recommendedIssue,
    recommendation_label: `基于第 ${latestIssue || "-"} 期开奖数据，生成第 ${recommendedIssue || "下一"} 期历史规则胆拖方案。`,
    front_dan: frontDan,
    front_tuo: frontTuo,
    back,
    front_dan_display: displayNumbers(frontDan),
    front_tuo_display: displayNumbers(frontTuo),
    back_display: displayNumbers(back),
    cost,
    tickets,
    reason: `按用户指定的 ${frontDan.length} 胆 ${frontTuo.length} 拖生成，费用 ${cost} 元。`,
    explanation: aiCommentaryForPlan({ mode: "dantuo" }, labels),
    score_basis: `${labels.front}和${labels.back}均先按热度0.4 + 遗漏0.3 + 历史结构平衡0.3评分；${labels.back}${back.map((number) => `${formatNumber(number)}(${backScoreMap.get(number)?.total_score ?? backScoreMap.get(number)?.score ?? 0}分)`).join("、")}。`,
    budget_analysis: {
      budget: Number(budget || 0),
      cost,
      unused: Math.max(0, Number(budget || 0) - cost),
      utilization: Number(budget || 0) ? Math.round((cost / Number(budget || 0)) * 10000) / 100 : 0,
      explanation: cost <= Number(budget || 0) ? "该胆拖结构符合当前预算。" : "该胆拖结构已超过预算，请减少拖码或后区数量。",
    },
  };
}

function manualCommentary({ plan, scoreRows, labels }) {
  const scoreMap = new Map((scoreRows || []).map((row) => [Number(row.number), row]));
  const frontNumbers = plan.mode === "dantuo" ? [...plan.front_dan, ...plan.front_tuo] : plan.items?.[0]?.front || [];
  const scored = frontNumbers.map((number) => scoreMap.get(number)?.total_score || 0).filter(Boolean);
  const average = scored.length ? scored.reduce((sum, value) => sum + value, 0) / scored.length : 0;
  const oddCount = frontNumbers.filter((number) => number % 2 === 1).length;
  const bigCount = frontNumbers.filter((number) => number > Math.ceil(Math.max(...frontNumbers, 1) / 2)).length;
  const notes = [
    `本方案${labels.front}平均评分约 ${average ? average.toFixed(1) : "-"}，可作为保存前的参考。`,
    `${labels.front}奇偶结构为 ${oddCount}:${frontNumbers.length - oddCount}，大号数量 ${bigCount} 个。`,
    plan.cost <= plan.budget_analysis.budget ? "费用在预算范围内，可以保存后等待开奖复盘。" : "费用超过预算，建议减少拖码或降低注数。",
  ];
  if (plan.mode === "dantuo" && plan.front_dan.length >= plan.front_tuo.length) {
    notes.push("胆码数量偏多，会降低拖码覆盖弹性，建议只把最有把握的号码放入胆码。");
  }
  return notes;
}

function buildManualBettingPlan({ scene, mode, selectedFront, selectedBack, frontDan, frontTuo, latestIssue, recommendedIssue, budget, scoreRows }) {
  const rules = sceneRules(scene);
  const labels = planLabelsForScene(scene);
  if (mode === "single") {
    if (selectedFront.length !== rules.frontPick || selectedBack.length !== rules.backPick) {
      throw new Error(`单式需要选择 ${rules.frontPick} 个${labels.front}和 ${rules.backPick} 个${labels.back}。`);
    }
    const item = {
      front: [...selectedFront].sort((left, right) => left - right),
      back: [...selectedBack].sort((left, right) => left - right),
      front_display: displayNumbers(selectedFront),
      back_display: displayNumbers(selectedBack),
      explanation: ["人工选号，系统按评分和结构给出点评。"],
    };
    const plan = {
      scene,
      play_name: rules.playName,
      play_labels: labels,
      mode: "single",
      source: "manual_selection",
      strategy: "manual_selection",
      based_on_issue: latestIssue,
      recommended_issue: recommendedIssue,
      recommendation_label: `人工选择第 ${recommendedIssue || "下一"} 期单式方案，保存后等待开奖复盘。`,
      budget_analysis: { budget: Number(budget || 0), cost: 2, unused: Math.max(0, Number(budget || 0) - 2), utilization: Number(budget || 0) ? Math.round((2 / Number(budget || 0)) * 10000) / 100 : 0 },
      cost: 2,
      tickets: 1,
      items: [item],
      reason: "人工选号方案，系统仅按历史评分和结构规则点评，不预测开奖结果。",
    };
    plan.explanation = manualCommentary({ plan, scoreRows, labels });
    return plan;
  }

  if (frontDan.length < 1 || frontDan.length >= rules.frontPick) {
    throw new Error(`胆拖需要至少 1 个${labels.dan}，且胆码少于 ${rules.frontPick} 个。`);
  }
  if (frontTuo.length < rules.frontPick - frontDan.length) {
    throw new Error(`${labels.tuo}数量不足，至少需要 ${rules.frontPick - frontDan.length} 个。`);
  }
  if (selectedBack.length < rules.backPick) {
    throw new Error(`${labels.back}至少需要选择 ${rules.backPick} 个。`);
  }
  const tickets = combinationCount(frontTuo.length, rules.frontPick - frontDan.length) * combinationCount(selectedBack.length, rules.backPick);
  const cost = tickets * 2;
  const plan = {
    scene,
    play_name: rules.playName,
    play_labels: labels,
    mode: "dantuo",
    source: "manual_selection",
    strategy: "manual_selection",
    based_on_issue: latestIssue,
    recommended_issue: recommendedIssue,
    recommendation_label: `人工选择第 ${recommendedIssue || "下一"} 期胆拖方案，保存后等待开奖复盘。`,
    front_dan: [...frontDan].sort((left, right) => left - right),
    front_tuo: [...frontTuo].sort((left, right) => left - right),
    back: [...selectedBack].sort((left, right) => left - right),
    front_dan_display: displayNumbers(frontDan),
    front_tuo_display: displayNumbers(frontTuo),
    back_display: displayNumbers(selectedBack),
    budget_analysis: {
      budget: Number(budget || 0),
      cost,
      unused: Math.max(0, Number(budget || 0) - cost),
      utilization: Number(budget || 0) ? Math.round((cost / Number(budget || 0)) * 10000) / 100 : 0,
      explanation: cost <= Number(budget || 0) ? "人工胆拖方案符合当前预算。" : "人工胆拖方案超过预算，请减少拖码或后区数量。",
    },
    cost,
    tickets,
    reason: "人工选号方案，系统仅按历史评分和结构规则点评，不预测开奖结果。",
  };
  plan.explanation = manualCommentary({ plan, scoreRows, labels });
  return plan;
}

function scoreSortLabel(sortKey) {
  const labels = {
    total_score: "综合分",
    heat_score: "热度分",
    missing_score: "遗漏分",
    balance_score: "均衡分",
  };
  return labels[sortKey] || "综合分";
}

const MODULE_NAV_ITEMS = [
  { key: "overview", label: "系统总览", icon: Home },
  { key: "data", label: "投注方案", icon: FileStack },
  { key: "review", label: "推荐复盘", icon: GitCompare },
  { key: "backtest", label: "历史回测", icon: Activity },
  { key: "trends", label: "走势分析", icon: TrendingUp },
  { key: "score", label: "号码评分", icon: Table2 },
  { key: "capital", label: "风险控制", icon: Coins },
  { key: "history", label: "历史记录", icon: History },
];

const MODULE_TITLES = MODULE_NAV_ITEMS.reduce((items, item) => ({
  ...items,
  [item.key]: item.label,
}), {});

function initialModuleFromUrl() {
  const requested = new URLSearchParams(window.location.search).get("module");
  return MODULE_NAV_ITEMS.some((item) => item.key === requested) ? requested : "overview";
}

function updateModuleUrl(module) {
  const url = new URL(window.location.href);
  url.searchParams.set("module", module);
  window.history.replaceState({}, "", url);
}

function AppSidebar({ scenes, active = "DLT", activeModule = "overview", onModuleChange, onSelect }) {
  return (
    <aside className="app-sidebar">
      <div className="brand-block">
        <div className="brand-mark">
          <span />
        </div>
        <div>
          <strong>策维</strong>
          <span>Digital Decision Platform</span>
        </div>
      </div>
      <nav className="side-nav" aria-label="场景导航">
        {MODULE_NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              aria-current={activeModule === item.key ? "page" : undefined}
              className={`side-nav-item ${activeModule === item.key ? "active" : ""}`}
              key={item.label}
              onClick={() => onModuleChange(item.key)}
              type="button"
            >
              <Icon size={18} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="scene-mini">
        {scenes.map((scene) => (
          <button
            className={`scene-mini-item ${active === scene.code ? "active" : ""}`}
            disabled={!scene.enabled}
            key={scene.code}
            onClick={() => scene.enabled && onSelect(scene.code)}
            type="button"
          >
            <span>{scene.name}</span>
            {scene.enabled ? "可用" : "规划中"}
          </button>
        ))}
      </div>

      <div className="side-footer">
        <h3>产品理念</h3>
        <p>策维不是彩票预测系统，而是帮助用户建立可解释、可控制预算、可持续优化的数字决策平台。</p>
        <p>历史数据分析 · 预算约束 · 资金控制</p>
      </div>
    </aside>
  );
}

function SceneSelect({ scenes, onEnter }) {
  const sceneDetails = {
    DLT: {
      title: "大乐透",
      code: "DLT",
      action: "进入系统",
    },
    SSQ: {
      title: "双色球",
      code: "SSQ",
      action: "进入系统",
    },
    K8: {
      title: "快乐8",
      code: "K8",
      action: "即将上线",
    },
    CUSTOM: {
      title: "自定义分析",
      code: "CUSTOM",
      action: "即将上线",
    },
  };

  return (
    <main className="scene-page">
      <header className="version-strip">
        {PRODUCT_STATUS.map((item) => (
          <div className={`version-pill ${item.tone}`} key={item.label}>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <em>{item.detail}</em>
          </div>
        ))}
      </header>

      <section className="scene-shell">
        <div className="scene-shell-title">
          <div>
            <Badge tone="live">场景选择页（所有版本通用）</Badge>
            <h1>策维（Ceway）数字决策平台</h1>
            <p>Digital Decision Platform · Powered by CBGO Framework。当前版本为 v1.8 验证闭环版，DLT 与 SSQ 共用完整决策闭环。</p>
          </div>
        </div>

        <section className="scene-grid">
          {scenes.map((scene) => {
            const detail = sceneDetails[scene.code] || scene;
            const description = scene.description || detail.description;
            const status = scene.status || (scene.enabled ? "可用" : "规划中");
            return (
              <button
                className={`scene-tile ${scene.enabled ? "" : "pending"}`}
                key={scene.code}
                onClick={() => onEnter(scene.code)}
                type="button"
              >
                <div className="scene-card-head">
                  <h2>{detail.title}</h2>
                  <Badge>{detail.code}</Badge>
                </div>
                <div className="scene-balls">
                  <SceneLogo code={detail.code} />
                </div>
                <p>{description}</p>
                {scene.enabled ? <Badge tone="live">{status}</Badge> : <Badge>{status}</Badge>}
                <span className="scene-action">{scene.enabled ? detail.action : "进入开发视图"}</span>
              </button>
            );
          })}
        </section>
      </section>

      <section className="baseline-panel">
        <div>
          <Badge tone="live">v1.8 验证闭环版</Badge>
          <h2>当前交付范围</h2>
          <p>选号只是入口；本版补齐方案比较、实际奖金复盘、跨设备同步和数据可追溯性。</p>
        </div>
        <div className="baseline-grid">
          <article>
            <h3>本版必须完成</h3>
            <ul>
              <li>大乐透与双色球双场景</li>
              <li>冷热号、遗漏、奇偶比、大小比、和值</li>
              <li>号码评分、单式、胆拖、预算控制</li>
              <li>保存、复盘、历史回测与风险控制</li>
            </ul>
          </article>
          <article>
            <h3>本版不开发</h3>
            <ul>
              <li>AI、论坛、舆情、外部数据 API</li>
              <li>任何中奖率或收益率承诺</li>
              <li>用历史命中结果预测下一期</li>
              <li>诱导追投、翻倍或亏损后加码</li>
            </ul>
          </article>
        </div>
      </section>

      <section className="roadmap-panel">
        <div>
          <Badge>后续迭代路线</Badge>
          <h2>版本规划</h2>
        </div>
        <div className="roadmap-grid">
          {ROADMAP_ITEMS.map((item) => (
            <article className="roadmap-card" key={item.version}>
              <Badge>{item.version}</Badge>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="disclaimer scene-disclaimer">
        <ShieldAlert size={16} />
        策维（Ceway）不预测开奖结果，不承诺提高中奖概率，仅提供基于历史数据的分析、预算管理与决策辅助。彩票具有随机性，请理性参与。
      </footer>
    </main>
  );
}

function ModulePlaceholder({ scene, scenes, onBack }) {
  const code = scene?.code || "CUSTOM";
  return (
    <main className="app-shell">
      <AppSidebar scenes={scenes} active={code} onSelect={() => {}} onBack={onBack} />
      <section className="workspace">
        <header className="workspace-topbar">
          <div>
            <Badge>{scene?.status || "规划中"}</Badge>
            <h1>{scene?.name || "自定义分析"} Module</h1>
            <p>Powered by CBGO Framework · 当前模块进入开发占位，后续按版本路线接入独立数据、评分和组合生成逻辑。</p>
          </div>
          <button className="ghost-button" onClick={onBack} type="button">
            <ArrowLeft size={16} />
            返回场景页
          </button>
        </header>

        <section className="module-placeholder">
          <SceneLogo code={code} />
          <div>
            <Badge>{scene?.module || `${code} Module`}</Badge>
            <h2>{scene?.name || "自定义分析"}</h2>
            <p>{scene?.description || "该模块正在规划中。"}</p>
            <ul>
              <li>独立历史数据结构</li>
              <li>独立走势分析引擎</li>
              <li>独立评分与组合生成策略</li>
              <li>独立预算与资金管理规则</li>
            </ul>
          </div>
        </section>
      </section>
    </main>
  );
}

function TrendPanel({ dashboard, scoreRows, windowSize, onWindowChange }) {
  const [activeTab, setActiveTab] = useState("hot");
  const missingByNumber = new Map(dashboard.trends.omissions.map((item) => [item.number, item.missing]));
  const scoreMap = new Map(scoreRows.map((item) => [item.number, item]));
  const hotFront = dashboard.trends.hot_front.slice(0, 35).map((item) => ({
    ...item,
    missing: missingByNumber.get(item.number) || 0,
  }));
  const sumValues = dashboard.trends.sum_values;
  const hottest = dashboard.trends.hot_front[0];
  const coldest = dashboard.trends.hot_front[dashboard.trends.hot_front.length - 1];
  const maxMissing = dashboard.trends.omissions.reduce((max, item) => item.missing > max.missing ? item : max, dashboard.trends.omissions[0]);
  const missingRows = dashboard.trends.omissions
    .map((item) => ({ ...item, score: scoreMap.get(item.number)?.total_score || 0 }))
    .sort((left, right) => right.missing - left.missing || right.score - left.score);
  const sumRangeRows = dashboard.trends.sum_values.map((item) => ({
    ...item,
    range: item.value < 75 ? "偏低" : item.value > 105 ? "偏高" : "均衡",
  }));
  const trendTabs = [
    { key: "hot", label: "冷热号" },
    { key: "missing", label: "遗漏" },
    { key: "odd", label: "奇偶比" },
    { key: "size", label: "大小比" },
    { key: "sum", label: "和值" },
  ];

  return (
    <section className="panel wide" id="module-trends">
      <div className="panel-title">
        <div>
          <h2>走势分析</h2>
          <p>最近 {dashboard.trends.window} 期历史开奖数据</p>
        </div>
        <div className="panel-actions">
          <select value={windowSize} onChange={(event) => onWindowChange(Number(event.target.value))}>
            <option value={30}>最近30期</option>
            <option value={50}>最近50期</option>
            <option value={100}>最近100期</option>
            <option value={200}>最近200期</option>
          </select>
          <Badge>最新 {dashboard.latest_issue}</Badge>
        </div>
      </div>

      <div className="trend-tabs">
        {trendTabs.map((tab) => (
          <button
            className={activeTab === tab.key ? "active" : ""}
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            type="button"
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === "hot" && (
        <div className="trend-layout">
          <div className="chart-box primary-chart">
            <h3>冷热号分布（近{dashboard.trends.window}期）</h3>
            <Suspense fallback={<ChartFallback />}>
              <TrendBarChartView data={hotFront} mode="hot" scoreRows={scoreRows} />
            </Suspense>
          </div>

          <div className="trend-stats">
            <h3>当前统计（前区）</h3>
            <dl>
              <div><dt>最热号码</dt><dd>{String(hottest.number).padStart(2, "0")}（{hottest.count}次）</dd></div>
              <div><dt>最冷号码</dt><dd>{String(coldest.number).padStart(2, "0")}（{coldest.count}次）</dd></div>
              <div><dt>最大遗漏</dt><dd>{String(maxMissing.number).padStart(2, "0")}（{maxMissing.missing}期）</dd></div>
              <div><dt>和值均值</dt><dd>{dashboard.trends.sum_range.avg}</dd></div>
            </dl>
          </div>

          <div className="chart-box sum-chart">
            <h3>和值走势</h3>
            <Suspense fallback={<ChartFallback height={170} />}>
              <TrendLineChartView data={sumValues} compact />
            </Suspense>
          </div>
        </div>
      )}

      {activeTab === "missing" && (
        <div className="trend-layout single">
          <div className="chart-box primary-chart">
            <h3>遗漏分布（前区35码）</h3>
            <Suspense fallback={<ChartFallback height={300} />}>
              <TrendBarChartView data={missingRows} mode="missing" />
            </Suspense>
          </div>
          <div className="trend-list">
            {missingRows.slice(0, 10).map((item) => (
              <div key={item.number}>
                <strong>{String(item.number).padStart(2, "0")}</strong>
                <span>遗漏 {item.missing} 期 · 综合分 {item.score}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(activeTab === "odd" || activeTab === "size") && (
        <div className="trend-layout single">
          <div className="chart-box primary-chart">
            <h3>{activeTab === "odd" ? "奇偶比历史分布" : "大小比历史分布"}</h3>
            <Suspense fallback={<ChartFallback height={300} />}>
              <TrendBarChartView data={activeTab === "odd" ? dashboard.trends.odd_even : dashboard.trends.big_small} mode="ratio" />
            </Suspense>
          </div>
          <div className="trend-list">
            {(activeTab === "odd" ? dashboard.trends.odd_even : dashboard.trends.big_small).map((item) => (
              <div key={item.ratio}>
                <strong>{item.ratio}</strong>
                <span>出现 {item.count} 期</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "sum" && (
        <div className="trend-layout single">
          <div className="chart-box primary-chart">
            <h3>和值走势与区间</h3>
            <Suspense fallback={<ChartFallback height={300} />}>
              <TrendLineChartView data={sumRangeRows} showDots />
            </Suspense>
          </div>
          <div className="trend-list">
            {sumRangeRows.slice(-10).reverse().map((item) => (
              <div key={item.issue}>
                <strong>{item.issue}</strong>
                <span>和值 {item.value} · {item.range}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="ratio-row">
        <div>
          <h3>奇偶比</h3>
          <div className="chips">
            {dashboard.trends.odd_even.map((item) => (
              <span key={item.ratio}>{item.ratio} · {item.count}</span>
            ))}
          </div>
        </div>
        <div>
          <h3>大小比</h3>
          <div className="chips">
            {dashboard.trends.big_small.map((item) => (
              <span key={item.ratio}>{item.ratio} · {item.count}</span>
            ))}
          </div>
        </div>
        <div>
          <h3>和值区间</h3>
          <div className="chips">
            <span>min {dashboard.trends.sum_range.min}</span>
            <span>avg {dashboard.trends.sum_range.avg}</span>
            <span>max {dashboard.trends.sum_range.max}</span>
          </div>
        </div>
      </div>
    </section>
  );
}

function ScoreTable({ rows, selectedNumbers = [] }) {
  const [sortKey, setSortKey] = useState("total_score");
  const [showAll, setShowAll] = useState(false);
  const [selectedRow, setSelectedRow] = useState(null);
  const selectedSet = useMemo(() => new Set(selectedNumbers.map(Number)), [selectedNumbers]);
  const sortedRows = useMemo(() => (
    [...rows].sort((left, right) => {
      const delta = (right[sortKey] || 0) - (left[sortKey] || 0);
      return delta || left.number - right.number;
    })
  ), [rows, sortKey]);
  const visibleRows = showAll ? sortedRows : sortedRows.slice(0, 15);

  return (
    <section className="panel" id="module-score">
      <div className="panel-title">
        <div>
          <h2>号码评分</h2>
          <p>热度 0.4 · 遗漏 0.3 · 均衡 0.3，当前按{scoreSortLabel(sortKey)}排序</p>
        </div>
        <div className="panel-actions">
          <select value={sortKey} onChange={(event) => setSortKey(event.target.value)}>
            <option value="total_score">综合分</option>
            <option value="heat_score">热度分</option>
            <option value="missing_score">遗漏分</option>
            <option value="balance_score">均衡分</option>
          </select>
          <button className="ghost-button compact" onClick={() => setShowAll(!showAll)} type="button">
            {showAll ? "只看Top15" : "查看全部"}
          </button>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>排名</th>
              <th>号码</th>
              <th>热度</th>
              <th>遗漏</th>
              <th>均衡</th>
              <th>综合</th>
              <th>解释</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row, index) => (
              <tr className={selectedRow?.number === row.number ? "selected" : ""} key={row.number}>
                <td>{row.rank || index + 1}</td>
                <td>
                  <button className="score-number-button" onClick={() => setSelectedRow(row)} type="button">
                    {String(row.number).padStart(2, "0")}
                  </button>
                  {selectedSet.has(Number(row.number)) && <Badge tone="live">已入选</Badge>}
                </td>
                <td>{row.heat_score}</td>
                <td>{row.missing_score}</td>
                <td>{row.balance_score}</td>
                <td className="score-hot">{row.total_score}</td>
                <td className="score-explanation">{row.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selectedRow && (
        <aside className="number-detail" aria-label={`号码${formatNumber(selectedRow.number)}详情`}>
          <div>
            <span>号码详情</span>
            <strong>{formatNumber(selectedRow.number)}</strong>
          </div>
          <dl>
            <div><dt>近期开奖出现</dt><dd>{selectedRow.heat_count ?? "-"} 次</dd></div>
            <div><dt>当前遗漏</dt><dd>{selectedRow.missing_periods ?? "-"} 期</dd></div>
            <div><dt>最近出现期号</dt><dd>{selectedRow.last_seen_issue || "暂无"}</dd></div>
            <div><dt>最近出现日期</dt><dd>{selectedRow.last_seen_date || "暂无"}</dd></div>
            <div><dt>综合评分</dt><dd>{selectedRow.total_score}</dd></div>
            <div><dt>本期方案</dt><dd>{selectedSet.has(Number(selectedRow.number)) ? "已入选" : "未入选"}</dd></div>
          </dl>
          <p>{selectedRow.explanation}</p>
          <button className="ghost-button compact" onClick={() => setSelectedRow(null)} type="button">关闭详情</button>
        </aside>
      )}
    </section>
  );
}

function DecisionBrief({ brief }) {
  if (!brief) return null;
  const RiskIcon = brief.risk_tone === "safe" ? CircleCheck : AlertTriangle;

  return (
    <section className={`decision-brief risk-${brief.risk_tone}`} aria-label="本期决策体检">
      <div className="decision-brief-head">
        <div>
          <span>本期决策体检</span>
          <strong>{brief.risk_level}风险</strong>
        </div>
        <RiskIcon size={20} />
      </div>
      <div className="decision-metrics">
        <div><span>实际支出</span><strong>{brief.cost} / {brief.budget} 元</strong></div>
        <div><span>买的是什么</span><strong>{brief.coverage_label}</strong></div>
        <div><span>投注倍率</span><strong>{brief.multiplier} 倍</strong></div>
        <div><span>本金暴露</span><strong>{brief.principal_exposure}%</strong></div>
        <div><span>近30日预计投入</span><strong>{brief.projected_period_spend} / {brief.period_cap} 元</strong></div>
        <div><span>连续加码</span><strong>{brief.escalation_detected ? "已触发提醒" : "未发现"}</strong></div>
      </div>
      <div className="decision-conclusion">
        <strong>系统结论</strong>
        <p>{brief.action}</p>
        <ul>{brief.signals.map((signal) => <li key={signal}>{signal}</li>)}</ul>
      </div>
      <div className="long-term-note">
        <strong>长期会怎样</strong>
        <p>{brief.history_message}</p>
      </div>
    </section>
  );
}

function CapitalPanel({
  capital,
  budget,
  principal,
  balance,
  lastPrize,
  levelUnits,
  periodCap,
  records,
  generated,
  backtest,
  onBudgetChange,
  onPrincipalChange,
  onBalanceChange,
  onLastPrizeChange,
  onLevelChange,
  onPeriodCapChange,
  onApply,
}) {
  const curve = cumulativeSpending(records).slice(-20);
  const currentPlan = generated || normalizeRecordPlan(records[0]);
  const brief = buildDecisionBrief({
    plan: currentPlan,
    budget,
    principal,
    periodCap,
    records: generated ? records : records.slice(1),
    backtest,
    capital,
  });
  const spent = recentSpending(records);

  return (
    <section className="panel wide capital-panel" id="module-capital">
      <div className="panel-title">
        <div>
          <h2>风险控制</h2>
          <p>看清支出、资金暴露和加码行为；未中奖不追投</p>
        </div>
        <Badge tone={brief?.risk_tone === "safe" ? "live" : "default"}>
          {brief ? `${brief.risk_level}风险` : "等待方案"}
        </Badge>
      </div>

      <div className="risk-settings">
        <label>本期上限<input min="2" step="2" type="number" value={budget} onChange={(event) => onBudgetChange(Number(event.target.value))} /></label>
        <label>近30日上限<input min="2" step="10" type="number" value={periodCap} onChange={(event) => onPeriodCapChange(Number(event.target.value))} /></label>
        <label>初始本金<input min="0" step="50" type="number" value={principal} onChange={(event) => onPrincipalChange(Number(event.target.value))} /></label>
        <label>当前余额<input min="0" step="10" type="number" value={balance} placeholder="默认等于本金" onChange={(event) => onBalanceChange(event.target.value === "" ? "" : Number(event.target.value))} /></label>
        <label>上期奖金<input min="0" step="1" type="number" value={lastPrize} onChange={(event) => onLastPrizeChange(Number(event.target.value))} /></label>
        <label>
          当前级别
          <select value={levelUnits} onChange={(event) => onLevelChange(Number(event.target.value))}>
            <option value={1}>1注</option>
            <option value={2}>2注</option>
            <option value={4}>4注</option>
          </select>
        </label>
        <button className="primary-button" onClick={onApply} type="button">
          <Activity size={16} />
          更新风险状态
        </button>
      </div>

      <div className="capital-grid">
        <div>
          <span>初始本金</span>
          <strong>{capital.principal} 元</strong>
        </div>
        <div>
          <span>当前余额</span>
          <strong>{capital.balance} 元</strong>
        </div>
        <div>
          <span>当前盈利</span>
          <strong>{capital.profit} 元</strong>
        </div>
        <div>
          <span>近30日已投入</span>
          <strong>{spent} 元</strong>
        </div>
        <div>
          <span>最大回撤</span>
          <strong>{capital.max_drawdown}%</strong>
        </div>
      </div>

      <DecisionBrief brief={brief} />

      <div className="capital-chart">
        <h3>累计投入（来自已保存方案）</h3>
        {curve.length > 0 ? (
          <Suspense fallback={<ChartFallback height={190} />}>
            <CapitalSpendChartView data={curve} />
          </Suspense>
        ) : <p className="empty-text">保存投注方案后，这里才会显示真实累计投入；系统不再展示示例资金曲线。</p>}
      </div>
      <div className="state-machine">
        <span className={capital.level_units === 1 ? "active" : ""}>1注</span>
        <span className={capital.level_units === 2 ? "active" : ""}>2注</span>
        <span className={capital.level_units === 4 ? "active" : ""}>4注</span>
      </div>
      <div className="transition-note">
        <strong>状态转移</strong>
        <p>{capital.transition_explanation || capital.transition?.explanation}</p>
      </div>
    </section>
  );
}

function DataStatusPanel({ dataStatus, onImport }) {
  if (!dataStatus) return null;
  const quality = dataStatus.quality;
  const isPublishedSnapshot = dataStatus.source === "published_snapshot"
    || dataStatus.storage === "published_snapshot";
  const lastSync = dataStatus.last_sync || {};
  const syncTime = lastSync.synced_at || dataStatus.synced_at || dataStatus.snapshot_updated_at || BUILD_TIME;
  const sourceName = dataStatus.source_name
    || lastSync.source
    || (isPublishedSnapshot ? "78500.cn + 官方开奖快照" : dataStatus.source_label || "本地 SQLite 数据库");

  return (
    <section className={`data-status-panel ${dataStatus.is_sample ? "sample" : ""}`}>
      <div>
        <Badge>{dataStatus.source_label}</Badge>
        <h2>数据状态</h2>
        <p>{dataStatus.message}</p>
        {quality && <p className="data-quality-message">{quality.message}</p>}
      </div>
      <dl>
        <div><dt>最新期号</dt><dd>{dataStatus.latest_issue || "-"}</dd></div>
        <div><dt>开奖日期</dt><dd>{dataStatus.latest_date || "-"}</dd></div>
        <div><dt>数据来源</dt><dd>{sourceName}</dd></div>
        <div><dt>快照同步</dt><dd>{syncTime ? new Date(syncTime).toLocaleString("zh-CN", { hour12: false }) : "-"}</dd></div>
        {quality && <div><dt>完整性</dt><dd>{quality.label}</dd></div>}
        <div><dt>数据文件</dt><dd>{dataStatus.path}</dd></div>
      </dl>
      {isPublishedSnapshot ? (
        <Badge>数据随网站版本更新</Badge>
      ) : (
        <label className="upload-button data-upload">
          <FileUp size={16} />
          导入最新CSV
          <input accept=".csv,text/csv" type="file" onChange={onImport} />
        </label>
      )}
    </section>
  );
}

function PlanCard({ plan, onSave }) {
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState(false);
  if (!plan) return null;
  const saveBlocked = plan.decision_brief?.risk_tone === "stop";

  const labels = {
    front: "前区",
    back: "后区",
    dan: "前区胆码",
    tuo: "前区拖码",
    single: "单式票",
    rule: "按当前场景规则生成预算内方案。",
    ...(plan.play_labels || {}),
  };
  const playName = plan.play_name || (plan.scene === "SSQ" ? "双色球" : "大乐透");

  const text = plan.mode === "dantuo"
    ? `${playName} ${planModeLabel(plan.mode)}\n${labels.dan}：${plan.front_dan_display.join(" ")}\n${labels.tuo}：${plan.front_tuo_display.join(" ")}\n${labels.back}：${plan.back_display.join(" ")}\n共 ${plan.tickets} 注，费用 ${plan.cost} 元`
    : `${playName} ${planModeLabel(plan.mode)}\n${plan.items.map((item, index) => `${index + 1}. ${labels.front} ${item.front_display.join(" ")} + ${labels.back} ${item.back_display.join(" ")}`).join("\n")}`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      window.prompt("当前浏览器不允许自动复制，请长按全选后复制：", text);
    }
  };

  const save = async () => {
    if (!onSave || saving) return;
    setSaving(true);
    try {
      await onSave(plan);
    } finally {
      setSaving(false);
    }
  };

  return (
    <article className="plan-card">
      <div className="plan-head">
        <Badge tone={plan.mode === "dantuo" ? "live" : "default"}>
          {plan.option_label || STRATEGY_LABELS[plan.strategy] || "策略"} · {planModeLabel(plan.mode)}
        </Badge>
        <strong>{plan.cost} 元 · {plan.tickets} 注</strong>
      </div>
      <div className="plan-issue">
        <span>推荐期号</span>
        <strong>{plan.recommended_issue ? `第 ${plan.recommended_issue} 期` : "下一期开奖"}</strong>
        <p>{plan.recommendation_label || "基于当前最新开奖数据生成下一期开奖推荐方案。"}</p>
      </div>
      {plan.budget_analysis && (
        <div className="budget-fit">
          <div>
            <span>预算匹配</span>
            <strong>{plan.budget_analysis.cost} / {plan.budget_analysis.budget} 元</strong>
          </div>
          <div>
            <span>预算占用</span>
            <strong>{plan.budget_analysis.utilization}%</strong>
          </div>
          <div>
            <span>未使用</span>
            <strong>{plan.budget_analysis.unused} 元</strong>
          </div>
          <p>{plan.budget_analysis.explanation}</p>
        </div>
      )}
      <p className="plan-rule">{labels.rule}</p>
      {plan.reason && <p className="plan-reason">{plan.reason}</p>}
      {plan.score_basis && <p className="plan-score-basis">{plan.score_basis}</p>}
      {plan.mode === "dantuo" ? (
        <div className="number-groups">
          <div>
            <p>{labels.dan}（{plan.front_dan_display.length}个）</p>
            <div>{plan.front_dan_display.map((item) => <NumberBall key={item} tone="dan">{item}</NumberBall>)}</div>
          </div>
          <div>
            <p>{labels.tuo}（{plan.front_tuo_display.length}个）</p>
            <div>{plan.front_tuo_display.map((item) => <NumberBall key={item}>{item}</NumberBall>)}</div>
          </div>
          <div>
            <p>{labels.back}（{plan.back_display.length}个）</p>
            <div>{plan.back_display.map((item) => <NumberBall key={item} tone="back">{item}</NumberBall>)}</div>
          </div>
        </div>
      ) : (
        <div className="single-list">
          {plan.items.slice(0, 8).map((item, index) => (
            <div className="single-ticket" key={`${item.front.join("-")}-${index}`}>
              <p><span>{labels.front}</span> {item.front_display.join(" ")} <span>{labels.back}</span> {item.back_display.join(" ")}</p>
              {item.explanation?.length > 0 && <span>{item.explanation[0]}</span>}
            </div>
          ))}
        </div>
      )}
      {plan.mode === "dantuo" && plan.explanation?.length > 0 && (
        <div className="number-explanations">
          {plan.explanation.map((item) => <span key={item}>{item}</span>)}
        </div>
      )}
      <DecisionBrief brief={plan.decision_brief} />
      <div className="plan-actions">
        <button className="icon-button text-button" onClick={copy} type="button">
          <Clipboard size={16} />
          {copied ? "已复制" : "复制方案"}
        </button>
        {onSave && (
          <button className="icon-button text-button" disabled={saving || saveBlocked} onClick={save} title={saveBlocked ? "请先按风险提示降低预算或停止连续加码" : "保存后等待开奖复盘"} type="button">
            <Save size={16} />
            {saving ? "保存中..." : saveBlocked ? "风险过高，暂不保存" : "保存方案"}
          </button>
        )}
      </div>
      {saveBlocked && <p className="save-blocked-note">先处理上方风险信号，再保存为待开奖方案。</p>}
    </article>
  );
}

function normalizeRecordPlan(record) {
  return record?.plan || record;
}

function SavedPlanDetails({ plan }) {
  const [copied, setCopied] = useState(false);
  const labels = plan.play_labels || planLabelsForScene(plan.scene || "DLT");
  const text = plan.mode === "dantuo"
    ? `${labels.dan}：${(plan.front_dan_display || displayNumbers(plan.front_dan || [])).join(" ")}\n${labels.tuo}：${(plan.front_tuo_display || displayNumbers(plan.front_tuo || [])).join(" ")}\n${labels.back}：${(plan.back_display || displayNumbers(plan.back || [])).join(" ")}`
    : (plan.items || []).map((item, index) => `${index + 1}. ${labels.front} ${(item.front_display || displayNumbers(item.front || [])).join(" ")} + ${labels.back} ${(item.back_display || displayNumbers(item.back || [])).join(" ")}`).join("\n");

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      window.prompt("当前浏览器不允许自动复制，请长按复制：", text);
    }
  };

  return (
    <div className="saved-plan-details">
      {plan.mode === "dantuo" ? (
        <div className="saved-number-groups">
          <div><span>{labels.dan}</span><strong>{(plan.front_dan_display || displayNumbers(plan.front_dan || [])).join(" ")}</strong></div>
          <div><span>{labels.tuo}</span><strong>{(plan.front_tuo_display || displayNumbers(plan.front_tuo || [])).join(" ")}</strong></div>
          <div><span>{labels.back}</span><strong>{(plan.back_display || displayNumbers(plan.back || [])).join(" ")}</strong></div>
        </div>
      ) : (
        <div className="saved-ticket-list">
          {(plan.items || []).map((item, index) => (
            <p key={`${index}-${(item.front || []).join("-")}`}>
              <b>{index + 1}</b> {labels.front} {(item.front_display || displayNumbers(item.front || [])).join(" ")} · {labels.back} {(item.back_display || displayNumbers(item.back || [])).join(" ")}
            </p>
          ))}
        </div>
      )}
      <div className="saved-plan-footer">
        <p>{plan.reason || plan.explanation?.[0] || "该方案保留生成时的号码与决策说明。"}</p>
        <button className="ghost-button compact" onClick={copy} type="button"><Clipboard size={14} />{copied ? "已复制" : "复制号码"}</button>
      </div>
    </div>
  );
}

function RecordSync({ scene, records, onImport }) {
  const [syncCode, setSyncCode] = useState("");
  const [importCode, setImportCode] = useState("");
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  const generate = async () => {
    const code = encodeSyncBundle(scene, records);
    setSyncCode(code);
    setStatus(`已生成 ${records.length} 条记录的同步码。`);
    try {
      await navigator.clipboard.writeText(code);
      setStatus(`已复制 ${records.length} 条记录的同步码。`);
    } catch {
      // The visible text area remains available for manual copying.
    }
  };

  const importRecords = async () => {
    setBusy(true);
    setStatus("");
    try {
      const bundle = decodeSyncBundle(importCode, scene);
      const count = await onImport(bundle.records);
      setStatus(`同步完成，新增 ${count} 条记录。`);
      setImportCode("");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="record-sync">
      <div className="record-sync-heading">
        <div>
          <strong>跨设备同步</strong>
          <span>同步码包含方案数据，不上传第三方；在另一台设备进入同一场景后导入。</span>
        </div>
        <button className="ghost-button compact" disabled={records.length === 0} onClick={generate} type="button">
          <Clipboard size={14} />生成同步码
        </button>
      </div>
      {syncCode && <textarea aria-label="导出的同步码" readOnly rows="3" value={syncCode} onFocus={(event) => event.target.select()} />}
      <div className="record-sync-import">
        <textarea aria-label="需要导入的同步码" rows="3" value={importCode} onChange={(event) => setImportCode(event.target.value)} placeholder="粘贴另一台设备生成的同步码" />
        <button className="primary-button" disabled={busy || !importCode.trim()} onClick={importRecords} type="button">
          {busy ? "正在导入..." : "导入同步码"}
        </button>
      </div>
      {status && <p className="record-sync-status">{status}</p>}
    </div>
  );
}

function HistoryRecords({ records, onDelete, review, scene, onImport }) {
  const [filter, setFilter] = useState("");
  const [expandedId, setExpandedId] = useState(null);
  const statusByRecord = useMemo(() => reviewStatusMap(review), [review]);
  const visibleRecords = records
    .filter((record) => !filter || `${record.latest_issue || ""}${record.strategy || ""}`.includes(filter))
    .slice(0, 8);
  return (
    <section className="panel wide history-panel" id="module-history">
      <div className="panel-title">
        <div>
          <h2>历史推荐记录</h2>
          <p>保存推荐时间、预算、模式、方案、费用和解释，支持期号/策略筛选</p>
        </div>
        <Badge>{records.length} 条</Badge>
      </div>
      <div className="inline-tools">
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="搜索期号或策略" />
      </div>
      <RecordSync scene={scene} records={records} onImport={onImport} />
      {visibleRecords.length === 0 ? (
        <p className="empty-text">暂无保存记录。进入“投注方案”生成系统建议或人工选号点评后，点击“保存方案”。</p>
      ) : (
        <div className="history-list">
          {visibleRecords.map((record) => {
            const plan = normalizeRecordPlan(record);
            const savedAt = record.saved_at ? new Date(record.saved_at).toLocaleString() : "-";
            const status = statusByRecord.get(record.id) || {};
            const statusText = record.review_status || status.label || "待复盘";
            const recordKey = record.id || `${savedAt}-${plan.mode}-${plan.cost}`;
            return (
              <article className={`history-item ${expandedId === recordKey ? "expanded" : ""}`} key={recordKey}>
                <div>
                  <strong>{STRATEGY_LABELS[record.strategy || plan.strategy] || "策略"} · {planModeLabel(plan.mode)}</strong>
                  <span>{savedAt} · 推荐期号 {plan.recommended_issue || record.latest_issue || "-"}</span>
                </div>
                <div>
                  <b>{plan.cost} 元</b>
                  <span>{plan.tickets} 注</span>
                </div>
                <Badge>{statusText}</Badge>
                <p>{status.nextStep || plan.reason || plan.explanation?.[0] || "该记录保留推荐方案和评分解释。"}</p>
                <div className="history-actions">
                  <button className="ghost-button compact" onClick={() => setExpandedId(expandedId === recordKey ? null : recordKey)} type="button">
                    {expandedId === recordKey ? "收起方案" : "查看方案"}
                  </button>
                  {record.id && (
                    <button className="ghost-button compact danger" onClick={() => onDelete(record.id)} type="button">删除记录</button>
                  )}
                </div>
                {expandedId === recordKey && <SavedPlanDetails plan={plan} />}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function ReviewPanel({ review, onRefresh }) {
  if (!review) return null;
  const summary = review.summary || {};
  return (
    <section className="panel wide review-panel" id="module-review">
      <div className="panel-title">
        <div>
          <h2>推荐复盘</h2>
          <p>对比已保存推荐方案与下一期开奖，统计历史命中表现</p>
        </div>
        <button className="ghost-button compact" onClick={onRefresh} type="button">刷新复盘</button>
      </div>
      <div className="review-summary">
        <div><span>已复盘</span><strong>{summary.reviewed || 0}</strong></div>
        <div><span>待开奖</span><strong>{summary.pending || 0}</strong></div>
        <div><span>投入金额</span><strong>{summary.total_cost || 0} 元</strong></div>
        <div><span>命中记录率</span><strong>{summary.record_hit_rate || 0}%</strong></div>
        <div><span>最佳命中</span><strong>{summary.best_hit || "-"}</strong></div>
        <div><span>最佳奖级</span><strong>{summary.best_prize_label || "-"}</strong></div>
        <div><span>实际奖金</span><strong>{summary.roi_complete ? `${summary.total_prize || 0} 元` : "部分待补"}</strong></div>
        <div><span>净收益</span><strong>{summary.roi_complete ? `${summary.net_profit || 0} 元` : "待奖金完整"}</strong></div>
        <div><span>实际 ROI</span><strong>{summary.roi_complete && summary.roi !== null ? `${summary.roi}%` : "待奖金完整"}</strong></div>
      </div>
      <div className="review-list">
        {(review.items || []).slice(0, 6).map((item) => (
          <article className="review-item" key={item.record_id || item.saved_at}>
            {(() => {
              const labels = lotteryLabels(item);
              return item.status === "pending" ? (
                <>
                  <div>
                    <strong>推荐期号 {item.recommended_issue || item.latest_issue || "-"}</strong>
                    <span>{item.next_step || item.message} 保存后会在这里进入“待开奖/待复盘”队列。</span>
                  </div>
                  <Badge>{item.status_label || "待开奖"}</Badge>
                </>
              ) : (
                <>
                  <div>
                    <strong>实际开奖 {item.actual.issue}</strong>
                    <span>{labels.front} {item.actual.front.map((number) => String(number).padStart(2, "0")).join(" ")} · {labels.back} {item.actual.back.map((number) => String(number).padStart(2, "0")).join(" ")}</span>
                  </div>
                  <div>
                    <b>{item.best?.hit_label || "-"}</b>
                    <span>{item.best?.prize_label || "-"}</span>
                  </div>
                  <Badge>{item.status_label || "已复盘"}</Badge>
                  <div className="review-compare">
                    <div>
                      <span>推荐号码</span>
                      <p>
                        {labels.front} {(item.best?.front || []).map((number) => String(number).padStart(2, "0")).join(" ")}
                        <br />
                        {labels.back} {(item.best?.back || []).map((number) => String(number).padStart(2, "0")).join(" ")}
                      </p>
                    </div>
                    <div>
                      <span>开奖号码</span>
                      <p>
                        {labels.front} {item.actual.front.map((number) => String(number).padStart(2, "0")).join(" ")}
                        <br />
                        {labels.back} {item.actual.back.map((number) => String(number).padStart(2, "0")).join(" ")}
                      </p>
                    </div>
                  </div>
                  <p>
                    推荐期号 {item.recommended_issue || item.latest_issue || "-"} · {planModeLabel(item.mode)} · {item.cost} 元 ·
                    命中票数 {item.hit_tickets}/{item.tickets} · 命中率 {item.hit_rate}%
                  </p>
                  {Object.keys(item.prize_distribution || {}).length > 0 && (
                    <p>奖级分布：{Object.entries(item.prize_distribution).map(([label, count]) => `${label} ${count} 注`).join("·")}</p>
                  )}
                  <p>
                    实际奖金 {item.prize_amount_complete ? `${item.prize_amount || 0} 元` : "奖金数据待补齐"}
                    {item.prize_amount_complete && ` · 净收益 ${item.net_profit || 0} 元 · ROI ${item.roi ?? 0}%`}
                  </p>
                  {item.prize_source && <p>奖金来源：{item.prize_source}</p>}
                </>
              );
            })()}
          </article>
        ))}
      </div>
      <p className="review-disclaimer">{review.disclaimer}</p>
    </section>
  );
}

function BacktestPanel({ backtest, onRefresh, strategy, onStrategyChange }) {
  if (!backtest) return null;
  const summary = backtest.summary || {};
  const baseline = backtest.baseline || {};
  const config = backtest.config || {};
  return (
    <section className="panel wide backtest-panel" id="module-backtest">
      <div className="panel-title">
        <div>
          <h2>历史回测</h2>
          <p>滚动使用历史数据生成方案，并与下一期开奖和随机选号对照</p>
        </div>
        <div className="panel-actions">
          <select aria-label="回测策略" value={strategy} onChange={(event) => onStrategyChange(event.target.value)}>
            <option value="conservative">保守策略</option>
            <option value="balanced">均衡策略</option>
            <option value="aggressive">覆盖策略</option>
          </select>
          <button className="ghost-button compact" onClick={onRefresh} type="button">
            <GitCompare size={14} />
            运行回测
          </button>
        </div>
      </div>
      <div className="backtest-summary">
        <div><span>回测期数</span><strong>{summary.periods || 0}</strong></div>
        <div><span>CBGO 命中记录率</span><strong>{summary.record_hit_rate || 0}%</strong></div>
        <div><span>随机对照</span><strong>{baseline.record_hit_rate || 0}%</strong></div>
        <div><span>相对差值</span><strong>{summary.edge_vs_random || 0}%</strong></div>
        <div><span>最佳命中</span><strong>{summary.best_hit || "-"}</strong></div>
        <div><span>最佳奖级</span><strong>{summary.best_prize_label || "-"}</strong></div>
      </div>
      <div className="backtest-grid">
        <div>
          <h3>CBGO 策略</h3>
          <p>平均前区命中 {summary.avg_front_hits || 0}，平均后区命中 {summary.avg_back_hits || 0}，投入 {summary.total_cost || 0} 元。</p>
        </div>
        <div>
          <h3>随机基线</h3>
          <p>平均前区命中 {baseline.avg_front_hits || 0}，平均后区命中 {baseline.avg_back_hits || 0}，投入 {baseline.total_cost || 0} 元。</p>
        </div>
      </div>
      <div className="backtest-list">
        {(backtest.items || []).slice(0, 8).map((item) => (
          <article className="backtest-item" key={`${item.source_issue}-${item.actual_issue}`}>
            <div>
              <strong>{item.source_issue} → {item.actual_issue}</strong>
              <span>{item.actual_date} · {planModeLabel(item.mode)} · {item.cost} 元</span>
            </div>
            <div>
              <b>{item.best?.hit_label || "-"}</b>
              <span>{item.best?.prize_label || "-"}</span>
            </div>
          </article>
        ))}
      </div>
      <p className="review-disclaimer">
        区间 {config.start_issue || "-"} 至 {config.end_issue || "-"} · 窗口 {config.window || "-"} 期。{backtest.disclaimer}
      </p>
    </section>
  );
}

function DataManagementPanel({ status, draws, onSearchDraws, onPageDraws, onSync }) {
  if (!status) return null;
  const quality = status.quality;
  const lastSync = status.last_sync;
  const isPublishedSnapshot = status.storage === "published_snapshot";
  const drawItems = Array.isArray(draws) ? draws : draws.items || [];
  const total = Array.isArray(draws) ? draws.length : draws.total || 0;
  const offset = Array.isArray(draws) ? 0 : draws.offset || 0;
  const limit = Array.isArray(draws) ? drawItems.length || 8 : draws.limit || 8;
  const currentIssue = Array.isArray(draws) ? "" : draws.issue || "";
  return (
    <section className="panel wide data-management-panel" id="module-data">
      <div className="panel-title">
        <div>
          <h2>数据管理</h2>
          <p>{isPublishedSnapshot ? "完整历史开奖快照、全量查询与完整性检查" : "SQLite 开奖数据、推荐记录、复盘结果与完整性检查"}</p>
        </div>
        <div className="panel-actions">
          {!isPublishedSnapshot && (
            <>
              <button className="ghost-button compact" onClick={() => onSync(false)} type="button">更新最新开奖</button>
              <button className="ghost-button compact" onClick={() => onSync(true)} type="button">全量校准</button>
            </>
          )}
          <Badge>{status.storage === "sqlite" ? "SQLite" : "完整历史快照"}</Badge>
        </div>
      </div>
      <div className="data-management-summary">
        <div><span>开奖数据</span><strong>{status.draw_count || 0} 期</strong></div>
        <div><span>推荐记录</span><strong>{status.record_count || 0} 条</strong></div>
        <div><span>复盘结果</span><strong>{status.review_count || 0} 条</strong></div>
        <div><span>最新期号</span><strong>{status.latest_issue || "-"}</strong></div>
        <div><span>首期数据</span><strong>{status.first_issue || "-"}</strong></div>
        <div><span>完整性</span><strong>{quality?.label || "-"}</strong></div>
      </div>
      {quality && (
        <div className={`quality-card ${quality.level || "unknown"}`}>
          <div>
            <strong>{quality.label}</strong>
            <p>{quality.message}</p>
          </div>
          <span>{quality.missing_count || 0} 个缺口</span>
          {quality.missing_issues?.length > 0 && (
            <p className="missing-issues">缺失期号：{quality.missing_issues.join("、")}</p>
          )}
        </div>
      )}
      {lastSync && (
        <div className="sync-card">
          <span>最近同步</span>
          <strong>{lastSync.source} · {lastSync.status === "ok" ? "成功" : "失败"}</strong>
          <p>{lastSync.synced_at} · {lastSync.message || "-"}</p>
        </div>
      )}
      <div className="inline-tools">
        <input
          defaultValue={currentIssue}
          onKeyDown={(event) => {
            if (event.key === "Enter") onSearchDraws(event.currentTarget.value.trim());
          }}
          placeholder="输入期号后回车搜索"
        />
        <span>共 {total} 期</span>
      </div>
      <div className="draw-list">
        {drawItems.map((draw) => (
          <article className="draw-item" key={draw.issue}>
            <div>
              <strong>{draw.issue}</strong>
              <span>{draw.date}</span>
            </div>
            <p>
              前区 {draw.front.map((number) => String(number).padStart(2, "0")).join(" ")}
              <br />
              后区 {draw.back.map((number) => String(number).padStart(2, "0")).join(" ")}
            </p>
          </article>
        ))}
      </div>
      <div className="pager-row">
        <button className="ghost-button compact" disabled={offset <= 0} onClick={() => onPageDraws(Math.max(0, offset - limit), currentIssue)} type="button">上一页</button>
        <span>{offset + 1} - {Math.min(offset + limit, total)} / {total}</span>
        <button className="ghost-button compact" disabled={offset + limit >= total} onClick={() => onPageDraws(offset + limit, currentIssue)} type="button">下一页</button>
      </div>
      <p className="data-management-note">当前数据库路径：{status.path}</p>
    </section>
  );
}

function NumberPicker({ title, max, selected, onToggle, tone = "front", helper }) {
  return (
    <div className="number-picker">
      <div className="picker-head">
        <strong>{title}</strong>
        <span>{selected.length} 个已选</span>
      </div>
      {helper && <p>{helper}</p>}
      <div className="picker-grid">
        {rangeNumbers(max).map((number) => {
          const active = selected.includes(number);
          return (
            <button
              className={`picker-ball ${tone} ${active ? "active" : ""}`}
              key={number}
              onClick={() => onToggle(number)}
              type="button"
            >
              {formatNumber(number)}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function PackageEvaluator({ scene, budget, onBudgetChange }) {
  const [multiplier, setMultiplier] = useState(1);
  const [giftConfirmed, setGiftConfirmed] = useState(false);
  const source = PACKAGE_SOURCES[scene];
  const rows = useMemo(
    () => packageCatalog(scene).map((item) => evaluatePackage(item, { multiplier, giftConfirmed, budget })),
    [scene, multiplier, giftConfirmed, budget],
  );
  const isSsq = scene === "SSQ";

  return (
    <div className="package-evaluator">
      <div className="package-context">
        <div>
          <span>当前口径</span>
          <strong>{source.label}</strong>
          <p>{source.region}。{source.activity}</p>
        </div>
        <a href={source.sourceUrl} rel="noreferrer" target="_blank">查看官方规则</a>
      </div>

      <div className="package-controls">
        <label>
          本期总预算
          <input min="2" step="2" type="number" value={budget} onChange={(event) => onBudgetChange(Number(event.target.value))} />
        </label>
        <label>
          套餐倍数
          <input min="1" max="20" step="1" type="number" value={multiplier} onChange={(event) => setMultiplier(Math.max(1, Number(event.target.value) || 1))} />
        </label>
        {isSsq && (
          <label className="package-confirm">
            <input checked={giftConfirmed} onChange={(event) => setGiftConfirmed(event.target.checked)} type="checkbox" />
            <span>当地终端已明确显示赠票成功</span>
          </label>
        )}
      </div>

      {isSsq && !giftConfirmed && (
        <p className="form-warning">活动有地区和资金限制，未确认前不把赠票计入覆盖与单注成本。</p>
      )}

      <div className="package-table-wrap">
        <table className="package-table">
          <thead>
            <tr>
              <th>套餐</th>
              <th>结构</th>
              <th>实付</th>
              <th>基础注数</th>
              <th>赠票</th>
              <th>票面展开</th>
              <th>单注实付</th>
              <th>预算</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.amount}>
                <td><strong>{row.amount}元</strong>{row.multiplier > 1 && <span>×{row.multiplier}</span>}</td>
                <td><span>{row.structure}</span>{row.giftTickets > 0 && <small>赠 {row.giftStructure}{row.blueDistinct ? "·蓝球扩展" : ""}</small>}</td>
                <td>{row.paid}元</td>
                <td>{row.baseTickets}注</td>
                <td>{row.giftAmount > 0 ? `${row.giftAmount}元 / ${row.giftTickets}注` : "未计入"}</td>
                <td>{row.faceAmount}元 / {row.totalTickets}注</td>
                <td>{row.unitPaidCost}元</td>
                <td><Badge tone={row.withinBudget ? "live" : "default"}>{row.withinBudget ? "预算内" : "超出"}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="package-notes">
        <p>“票面展开注数”按单式与复式组合公式计算，不代表不重复号码数，也不表示中奖概率被额外改变。</p>
        <p>套餐评估只比较固定预算内的实付与覆盖；倍投会同比增加支出，系统不因赠票建议追加预算。</p>
      </div>
    </div>
  );
}

function BettingPlanPanel({
  scene,
  dashboard,
  scoreRows,
  backScoreRows,
  budget,
  onBudgetChange,
  onSave,
  generated,
  onGenerated,
  decisionContext,
}) {
  const rules = sceneRules(scene);
  const labels = planLabelsForScene(scene);
  const [flow, setFlow] = useState("ai");
  const [mode, setMode] = useState("dantuo");
  const [ticketCount, setTicketCount] = useState(5);
  const [danCount, setDanCount] = useState(scene === "SSQ" ? 3 : 2);
  const [tuoCount, setTuoCount] = useState(scene === "SSQ" ? 5 : 5);
  const [backCount, setBackCount] = useState(rules.backPick);
  const [manualFront, setManualFront] = useState([]);
  const [manualBack, setManualBack] = useState([]);
  const [manualDan, setManualDan] = useState([]);
  const [manualTuo, setManualTuo] = useState([]);
  const [message, setMessage] = useState("");
  const variantStorageKey = `ceway_${scene.toLowerCase()}_suggestion_variant`;
  const [variant, setVariant] = useState(() => Number(sessionStorage.getItem(variantStorageKey) || 0));

  const revealGenerated = () => {
    window.requestAnimationFrame(() => {
      document.getElementById("generated-plan-result")?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  };

  const toggleNumber = (list, setList, number, limit = Infinity) => {
    setMessage("");
    setList((items) => {
      if (items.includes(number)) return items.filter((item) => item !== number);
      if (items.length >= limit) return items;
      return [...items, number].sort((left, right) => left - right);
    });
  };

  const toggleDan = (number) => {
    setMessage("");
    setManualTuo((items) => items.filter((item) => item !== number));
    toggleNumber(manualDan, setManualDan, number, rules.frontPick - 1);
  };

  const toggleTuo = (number) => {
    setMessage("");
    setManualDan((items) => items.filter((item) => item !== number));
    toggleNumber(manualTuo, setManualTuo, number);
  };

  const createAiPlan = () => {
    try {
      const nextVariant = variant + 1;
      const optionSpecs = [
        { optionLabel: "主推方案", optionMode: mode, offset: 0 },
        { optionLabel: "备选方案 A", optionMode: mode, offset: 1 },
        { optionLabel: "备选方案 B", optionMode: mode, offset: 2 },
        { optionLabel: "单式兜底", optionMode: "single", offset: 3 },
      ];
      const comparisonPlans = optionSpecs.map(({ optionLabel, optionMode, offset }) => {
        const plan = buildAiBettingPlan({
          scene,
          scoreRows,
          backScoreRows,
          budget,
          mode: optionMode,
          ticketCount: optionMode === "single" ? Math.max(1, Math.min(3, Math.floor(Number(budget || 0) / 2))) : ticketCount,
          danCount,
          tuoCount,
          backCount,
          latestIssue: dashboard.latest_issue,
          recommendedIssue: dashboard.recommended_issue,
          variant: nextVariant + offset,
        });
        return {
          ...plan,
          option_label: optionLabel,
          generation_variant: nextVariant + offset,
          decision_brief: buildDecisionBrief({ plan, budget, ...decisionContext }),
        };
      });
      const plan = comparisonPlans[0];
      const followingVariant = nextVariant + optionSpecs.length;
      setVariant(followingVariant);
      sessionStorage.setItem(variantStorageKey, String(followingVariant));
      onGenerated({ ...plan, comparison_plans: comparisonPlans });
      setMessage(plan.cost <= Number(budget || 0) ? `第 ${nextVariant} 批建议已生成，可比较主推、备选和单式兜底。` : "方案已生成，但费用超过预算，请调整胆拖数量。");
      revealGenerated();
    } catch (err) {
      setMessage(err.message);
    }
  };

  const createManualPlan = () => {
    try {
      const plan = buildManualBettingPlan({
        scene,
        mode,
        selectedFront: manualFront,
        selectedBack: manualBack,
        frontDan: manualDan,
        frontTuo: manualTuo,
        latestIssue: dashboard.latest_issue,
        recommendedIssue: dashboard.recommended_issue,
        budget,
        scoreRows,
      });
      const decisionBrief = buildDecisionBrief({ plan, budget, ...decisionContext });
      onGenerated({ ...plan, decision_brief: decisionBrief });
      setMessage("人工方案已生成点评，可保存后进入待开奖复盘。");
      revealGenerated();
    } catch (err) {
      setMessage(err.message);
    }
  };

  const clearManual = () => {
    setManualFront([]);
    setManualBack([]);
    setManualDan([]);
    setManualTuo([]);
    setMessage("");
  };

  const estimatedTickets = mode === "dantuo"
    ? combinationCount(Number(tuoCount || 0), rules.frontPick - Number(danCount || 0)) * combinationCount(Number(backCount || 0), rules.backPick)
    : Number(ticketCount || 0);
  const estimatedCost = Math.max(0, estimatedTickets * 2);

  return (
    <section className="panel wide betting-panel" id="module-data">
      <div className="panel-title">
        <div>
          <h2>投注方案</h2>
          <p>先选择系统建议或人工选号，再生成方案、保存记录，等待开奖后自动复盘。</p>
        </div>
        <Badge tone="live">第 {dashboard.recommended_issue || "下一"} 期</Badge>
      </div>

      <div className="workflow-tabs">
        <button className={flow === "ai" ? "active" : ""} onClick={() => setFlow("ai")} type="button">
          <Sparkles size={16} />
          系统建议
        </button>
        <button className={flow === "manual" ? "active" : ""} onClick={() => setFlow("manual")} type="button">
          <Table2 size={16} />
          人工选号点评
        </button>
        <button className={flow === "package" ? "active" : ""} onClick={() => setFlow("package")} type="button">
          <WalletCards size={16} />
          套餐评估
        </button>
      </div>

      <div className={`betting-workspace ${flow}-workspace`}>
        {flow !== "package" && <div className="betting-controls">
          <div className="field-grid compact-fields">
            <label>
              本期预算
              <input min="2" step="2" type="number" value={budget} onChange={(event) => onBudgetChange(Number(event.target.value))} />
            </label>
            <label>
              玩法
              <select value={mode} onChange={(event) => setMode(event.target.value)}>
                <option value="dantuo">胆拖</option>
                <option value="single">单式</option>
              </select>
            </label>
            {flow === "ai" && mode === "single" && (
              <label>
                注数
                <input min="1" step="1" type="number" value={ticketCount} onChange={(event) => setTicketCount(Number(event.target.value))} />
              </label>
            )}
            {flow === "ai" && mode === "dantuo" && (
              <>
                <label>
                  胆数
                  <input min="1" max={rules.frontPick - 1} step="1" type="number" value={danCount} onChange={(event) => setDanCount(Number(event.target.value))} />
                </label>
                <label>
                  拖数
                  <input min={rules.frontPick - danCount} step="1" type="number" value={tuoCount} onChange={(event) => setTuoCount(Number(event.target.value))} />
                </label>
                <label>
                  {labels.back}数量
                  <input min={rules.backPick} max={rules.backMax} step="1" type="number" value={backCount} onChange={(event) => setBackCount(Number(event.target.value))} />
                </label>
              </>
            )}
          </div>

          {flow === "ai" ? (
            <div className="betting-estimate">
              <div><span>预计注数</span><strong>{estimatedTickets || 0} 注</strong></div>
              <div><span>预计费用</span><strong>{estimatedCost || 0} 元</strong></div>
              <div><span>预算状态</span><strong>{estimatedCost <= Number(budget || 0) ? "符合" : "超出"}</strong></div>
              <button className="primary-button strong" onClick={createAiPlan} type="button">
                <Play size={16} />
                {generated?.source === "rule_suggestion" ? "再生成一组" : "生成系统建议"}
              </button>
            </div>
          ) : (
            <div className="manual-actions">
              <p>人工选号不会预测开奖，只根据你选的号码做结构点评，并保存到复盘队列。</p>
              <div>
                <button className="primary-button strong" onClick={createManualPlan} type="button">
                  <Sparkles size={16} />
                  生成点评
                </button>
                <button className="ghost-button" onClick={clearManual} type="button">清空选择</button>
              </div>
            </div>
          )}
          {message && <p className={message.includes("超过") || message.includes("需要") || message.includes("不足") ? "form-warning" : "form-success"}>{message}</p>}
        </div>}

        {flow === "manual" && (
          <div className="manual-picker">
            {mode === "single" ? (
              <>
                <NumberPicker
                  title={`${labels.front}（选 ${rules.frontPick} 个）`}
                  max={rules.frontMax}
                  selected={manualFront}
                  onToggle={(number) => toggleNumber(manualFront, setManualFront, number, rules.frontPick)}
                  helper="用于生成一注人工单式方案。"
                />
                <NumberPicker
                  title={`${labels.back}（选 ${rules.backPick} 个）`}
                  max={rules.backMax}
                  selected={manualBack}
                  onToggle={(number) => toggleNumber(manualBack, setManualBack, number, rules.backPick)}
                  tone="back"
                />
              </>
            ) : (
              <>
                <NumberPicker
                  title={labels.dan}
                  max={rules.frontMax}
                  selected={manualDan}
                  onToggle={toggleDan}
                  tone="dan"
                  helper={`胆码少于 ${rules.frontPick} 个，只放最想保留的核心号码。`}
                />
                <NumberPicker
                  title={labels.tuo}
                  max={rules.frontMax}
                  selected={manualTuo}
                  onToggle={toggleTuo}
                  helper="拖码用于扩展组合覆盖，拖码越多费用越高。"
                />
                <NumberPicker
                  title={labels.back}
                  max={rules.backMax}
                  selected={manualBack}
                  onToggle={(number) => toggleNumber(manualBack, setManualBack, number)}
                  tone="back"
                />
              </>
            )}
          </div>
        )}
        {flow === "package" && (
          <PackageEvaluator scene={scene} budget={budget} onBudgetChange={onBudgetChange} />
        )}
      </div>

      {generated && flow !== "package" && (
        <div className="betting-result" id="generated-plan-result">
          <div className="section-kicker">
            <span>{generated.source === "manual_selection" ? "人工方案点评" : "系统方案比较"}</span>
            <strong>{generated.source === "manual_selection" ? `${generated.cost} 元 · ${generated.tickets} 注` : "4 个方案独立保存"}</strong>
          </div>
          <div className={generated.comparison_plans?.length ? "plan-comparison-grid" : ""}>
            {(generated.comparison_plans || [generated]).map((plan) => (
              <PlanCard
                key={`${plan.option_label || "manual"}-${plan.generation_variant || 0}`}
                plan={plan}
                onSave={onSave}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function Dashboard({ scenes, onBack, onSceneSelect }) {
  const [budget, setBudget] = useState(20);
  const [lastPrize, setLastPrize] = useState(0);
  const [strategy, setStrategy] = useState("balanced");
  const [windowSize, setWindowSize] = useState(100);
  const [principal, setPrincipal] = useState(1000);
  const [balance, setBalance] = useState("");
  const [levelUnits, setLevelUnits] = useState(1);
  const [periodCap, setPeriodCap] = useState(200);
  const [activeModule, setActiveModule] = useState(initialModuleFromUrl);
  const [dashboard, setDashboard] = useState(null);
  const [generated, setGenerated] = useState(null);
  const [savedPlans, setSavedPlans] = useState([]);
  const [review, setReview] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [dataStorage, setDataStorage] = useState(null);
  const [draws, setDraws] = useState([]);
  const [drawIssue, setDrawIssue] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const changeModule = (module) => {
    setActiveModule(module);
    updateModuleUrl(module);
  };

  const loadDashboard = async (overrides = {}) => {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const data = await getDltDashboard({
        budget,
        lastPrize,
        strategy,
        window: typeof overrides.window === "number" ? overrides.window : windowSize,
        principal,
        balance,
        levelUnits,
      });
      setDashboard(data);
      setGenerated(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    getDltRecords()
      .then((records) => setSavedPlans(records))
      .catch(() => {
        const stored = JSON.parse(localStorage.getItem("cbgo_saved_plans") || "[]");
        setSavedPlans(stored);
      });
    getDltReview()
      .then(setReview)
      .catch(() => setReview({
        summary: { reviewed: 0, pending: 0, total_cost: 0, record_hit_rate: 0, best_hit: "-", best_prize_label: "-" },
        items: [],
        disclaimer: "复盘数据暂不可用，已跳过异常记录。",
      }));
    getDltBacktest({ budget, strategy, periods: 100, window: windowSize })
      .then(setBacktest)
      .catch(() => setBacktest(null));
    getDltDataStatus().then(setDataStorage).catch(() => setDataStorage(null));
    getDltDraws({ limit: 12 }).then(setDraws).catch(() => setDraws({ items: [], total: 0, limit: 12, offset: 0, issue: "" }));
  }, []);

  const refreshDataStorage = async ({ offset = 0, issue = drawIssue } = {}) => {
    const [status, drawPayload] = await Promise.all([
      getDltDataStatus(),
      searchDltDraws({ limit: 12, offset, issue }),
    ]);
    setDataStorage(status);
    setDraws(drawPayload);
    setDrawIssue(issue);
  };

  const refreshReview = async () => {
    try {
      const data = await getDltReview();
      setReview(data);
    } catch (err) {
      setReview({
        summary: { reviewed: 0, pending: 0, total_cost: 0, record_hit_rate: 0, best_hit: "-", best_prize_label: "-" },
        items: [],
        disclaimer: `复盘数据暂不可用：${err.message}`,
      });
    }
  };

  const refreshBacktest = async () => {
    setError("");
    setNotice("正在运行历史回测...");
    try {
      const data = await getDltBacktest({ budget, strategy, periods: 100, window: windowSize });
      setBacktest(data);
      setNotice(`历史回测完成：${data.summary?.periods || 0} 期，命中记录率 ${data.summary?.record_hit_rate || 0}%。`);
    } catch (err) {
      setError(err.message);
      setNotice("");
    }
  };

  const syncHistory = async (full = false) => {
    setError("");
    setNotice(full ? "正在全量校准开奖数据..." : "正在更新最新开奖数据...");
    try {
      const result = await syncDltHistory({ source: "78500", full });
      await loadDashboard();
      await refreshDataStorage({ offset: 0, issue: "" });
      setNotice(`开奖数据更新完成：最新期号 ${result.data_status?.latest_issue || "-"}`);
    } catch (err) {
      setError(err.message);
    }
  };

  const deleteRecord = async (id) => {
    setError("");
    try {
      await deleteDltRecord(id);
      setSavedPlans((items) => items.filter((record) => record.id !== id));
      await refreshReview();
      setNotice("历史推荐记录已删除。");
    } catch (err) {
      setError(err.message);
    }
  };

  const topNumbers = useMemo(() => {
    if (!dashboard) return "-";
    return dashboard.top_numbers.map((number) => String(number).padStart(2, "0")).join(" ");
  }, [dashboard]);

  const savePlan = async (plan) => {
    const localRecord = {
      id: `${Date.now()}-${plan.strategy}-${plan.mode}`,
      saved_at: new Date().toISOString(),
      budget,
      strategy,
      latest_issue: dashboard.latest_issue,
      plan,
    };
    try {
      const result = await saveDltRecord({
        budget,
        strategy,
        latestIssue: dashboard.latest_issue,
        plan,
      });
      setSavedPlans((items) => [result.record, ...items].slice(0, 100));
      await refreshReview();
      changeModule("history");
      setNotice("方案已保存到后端历史记录。");
    } catch (err) {
      const nextPlans = [localRecord, ...savedPlans].slice(0, 20);
      localStorage.setItem("cbgo_saved_plans", JSON.stringify(nextPlans));
      setSavedPlans(nextPlans);
      await refreshReview();
      changeModule("history");
      setNotice(`后端保存失败，方案已保存到本地浏览器。${err?.message ? `原因：${err.message}` : ""}`);
    }
  };

  const importSyncedRecords = async (records) => {
    const signatures = new Set(savedPlans.map((record) => JSON.stringify(normalizeRecordPlan(record))));
    const incoming = records.filter((record) => {
      const plan = normalizeRecordPlan(record);
      const signature = JSON.stringify(plan);
      if (!plan?.mode || signatures.has(signature)) return false;
      signatures.add(signature);
      return true;
    });
    const saved = await Promise.all(incoming.map((record) => saveDltRecord({
      budget: Number(record.budget || record.plan?.cost || 0),
      strategy: record.strategy || record.plan?.strategy || "balanced",
      latestIssue: record.latest_issue || record.plan?.recommended_issue || dashboard.latest_issue,
      plan: normalizeRecordPlan(record),
    })));
    if (saved.length) {
      const refreshed = await getDltRecords();
      setSavedPlans(refreshed);
      await refreshReview();
    }
    return saved.length;
  };

  const importHistory = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setNotice("");
    try {
      const result = await importDltHistory(file);
      await loadDashboard();
      await refreshDataStorage({ offset: 0, issue: "" });
      setNotice(`已导入 ${result.rows} 期历史开奖数据。`);
    } catch (err) {
      setError(err.message);
    } finally {
      event.target.value = "";
    }
  };

  const isPublishedSnapshot = dashboard?.data_status?.source === "published_snapshot";

  if (loading) {
    return <main className="loading"><RefreshCw className="spin" /> 正在计算 DLT Module 数据...</main>;
  }

  if (error && !dashboard) {
    const fatalError = classifyError(error, "数据加载失败");
    return (
      <main className="loading">
        <ShieldAlert />
        <strong>{fatalError.title}</strong>
        <p>{fatalError.detail}</p>
        <button className="text-button" onClick={onBack} type="button">返回</button>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <AppSidebar
        scenes={scenes}
        active="DLT"
        activeModule={activeModule}
        onModuleChange={changeModule}
        onSelect={onSceneSelect}
      />

      <section className="workspace">
        <header className="workspace-topbar">
          <div>
            <Badge tone="live">大乐透 DLT</Badge>
            <h1>策维（Ceway）数字决策平台</h1>
            <p>Powered by CBGO Framework · DLT Module　当前期号：{dashboard.latest_issue}　数据截至：{dashboard.data_status?.latest_date || "-"}　<span className="status-dot" />运行状态：正常</p>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={onBack} type="button">
              <ArrowLeft size={16} />
              返回场景页
            </button>
            <Badge><Database size={13} /> {dashboard.history_count} 期历史记录</Badge>
            {!isPublishedSnapshot && (
              <label className="upload-button">
                <FileUp size={16} />
                导入CSV
                <input accept=".csv,text/csv" type="file" onChange={importHistory} />
              </label>
            )}
            <button className="icon-button" onClick={loadDashboard} title="刷新" type="button">
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        <ErrorNotice error={error} onRetry={loadDashboard} />
        {notice && <p className="notice">{notice}</p>}

        <section className="module-stage" aria-label={MODULE_TITLES[activeModule]}>
          {activeModule === "overview" && (
            <>
              <section className="stats" id="module-overview">
                <TopNumbersCard rows={dashboard.score_table} />
                <StatCard icon={Gauge} label="当前下注状态" value={dashboard.capital_state.level} meta={`下一状态 ${dashboard.capital_state.next_level}`} />
                <StatCard icon={WalletCards} label="当前资金" value={`${dashboard.capital_state.balance} 元`} meta={`盈利 ${dashboard.capital_state.profit} 元`} />
                <StatCard icon={Coins} label="本期预算" value={`${budget} 元`} meta="进入投注方案生成或人工选号" />
              </section>
              <DataStatusPanel dataStatus={dashboard.data_status} onImport={importHistory} />
            </>
          )}

          {activeModule === "data" && (
            <BettingPlanPanel
              scene="DLT"
              dashboard={dashboard}
              scoreRows={dashboard.score_table}
              backScoreRows={dashboard.back_scoreboard}
              budget={budget}
              onBudgetChange={setBudget}
              generated={generated}
              onGenerated={setGenerated}
              onSave={savePlan}
              decisionContext={{ principal, periodCap, records: savedPlans, backtest, capital: dashboard.capital_state }}
            />
          )}

          {activeModule === "review" && <ReviewPanel review={review} onRefresh={refreshReview} />}
          {activeModule === "backtest" && <BacktestPanel backtest={backtest} onRefresh={refreshBacktest} strategy={strategy} onStrategyChange={setStrategy} />}
          {activeModule === "trends" && (
            <TrendPanel
              dashboard={dashboard}
              scoreRows={dashboard.score_table}
              windowSize={windowSize}
              onWindowChange={(value) => {
                setWindowSize(value);
                loadDashboard({ window: value });
              }}
            />
          )}
          {activeModule === "score" && <ScoreTable rows={dashboard.score_table} selectedNumbers={planFrontNumbers(generated)} />}
          {activeModule === "capital" && (
            <CapitalPanel
              capital={dashboard.capital_state}
              budget={budget}
              principal={principal}
              balance={balance}
              lastPrize={lastPrize}
              levelUnits={levelUnits}
              periodCap={periodCap}
              records={savedPlans}
              generated={generated}
              backtest={backtest}
              onBudgetChange={setBudget}
              onPrincipalChange={setPrincipal}
              onBalanceChange={setBalance}
              onLastPrizeChange={setLastPrize}
              onLevelChange={setLevelUnits}
              onPeriodCapChange={setPeriodCap}
              onApply={loadDashboard}
            />
          )}
          {activeModule === "history" && <HistoryRecords records={savedPlans} onDelete={deleteRecord} review={review} scene="DLT" onImport={importSyncedRecords} />}
        </section>

        <footer className="disclaimer footer-note">
          <ShieldAlert size={16} />
          {dashboard.disclaimer} 彩票具有随机性，请理性娱乐，量力而行。
        </footer>
      </section>
    </main>
  );
}

function SsqDashboard({ scenes, onBack, onSceneSelect }) {
  const [budget, setBudget] = useState(20);
  const [lastPrize, setLastPrize] = useState(0);
  const [strategy, setStrategy] = useState("balanced");
  const [windowSize, setWindowSize] = useState(100);
  const [principal, setPrincipal] = useState(1000);
  const [balance, setBalance] = useState("");
  const [levelUnits, setLevelUnits] = useState(1);
  const [periodCap, setPeriodCap] = useState(200);
  const [activeModule, setActiveModule] = useState(initialModuleFromUrl);
  const [dashboard, setDashboard] = useState(null);
  const [generated, setGenerated] = useState(null);
  const [savedPlans, setSavedPlans] = useState([]);
  const [review, setReview] = useState(null);
  const [backtest, setBacktest] = useState(null);
  const [dataStorage, setDataStorage] = useState(null);
  const [draws, setDraws] = useState([]);
  const [drawIssue, setDrawIssue] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const changeModule = (module) => {
    setActiveModule(module);
    updateModuleUrl(module);
  };

  const loadDashboard = async (overrides = {}) => {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const data = await getSsqDashboard({
        budget,
        lastPrize,
        strategy,
        window: typeof overrides.window === "number" ? overrides.window : windowSize,
        principal,
        balance,
        levelUnits,
      });
      setDashboard(data);
      setGenerated(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadDashboard();
    getSsqRecords()
      .then((records) => setSavedPlans(records))
      .catch(() => {
        const stored = JSON.parse(localStorage.getItem("cbgo_ssq_plans") || "[]");
        setSavedPlans(stored);
      });
    getSsqReview()
      .then(setReview)
      .catch(() => setReview({
        summary: { reviewed: 0, pending: 0, total_cost: 0, record_hit_rate: 0, best_hit: "-", best_prize_label: "-" },
        items: [],
        disclaimer: "SSQ 复盘数据暂不可用。",
      }));
    getSsqBacktest({ budget, strategy, periods: 100, window: windowSize })
      .then(setBacktest)
      .catch(() => setBacktest(null));
    getSsqDataStatus().then(setDataStorage).catch(() => setDataStorage(null));
    getSsqDraws({ limit: 12 }).then(setDraws).catch(() => setDraws({ items: [], total: 0, limit: 12, offset: 0, issue: "" }));
  }, []);

  const refreshDataStorage = async ({ offset = 0, issue = drawIssue } = {}) => {
    const [status, drawPayload] = await Promise.all([
      getSsqDataStatus(),
      searchSsqDraws({ limit: 12, offset, issue }),
    ]);
    setDataStorage(status);
    setDraws(drawPayload);
    setDrawIssue(issue);
  };

  const refreshReview = async () => {
    try {
      const data = await getSsqReview();
      setReview(data);
    } catch (err) {
      setReview({
        summary: { reviewed: 0, pending: 0, total_cost: 0, record_hit_rate: 0, best_hit: "-", best_prize_label: "-" },
        items: [],
        disclaimer: `SSQ 复盘数据暂不可用：${err.message}`,
      });
    }
  };

  const refreshBacktest = async () => {
    setError("");
    setNotice("正在运行双色球历史回测...");
    try {
      const data = await getSsqBacktest({ budget, strategy, periods: 100, window: windowSize });
      setBacktest(data);
      setNotice(`双色球回测完成：${data.summary?.periods || 0} 期，命中记录率 ${data.summary?.record_hit_rate || 0}%。`);
    } catch (err) {
      setError(err.message);
      setNotice("");
    }
  };

  const syncHistory = async (full = false) => {
    setError("");
    setNotice(full ? "正在全量校准双色球开奖数据..." : "正在更新双色球开奖数据...");
    try {
      const result = await syncSsqHistory({ source: "78500", full });
      await loadDashboard();
      await refreshDataStorage({ offset: 0, issue: "" });
      setNotice(`双色球数据更新完成：最新期号 ${result.data_status?.latest_issue || "-"}`);
    } catch (err) {
      setError(err.message);
      setNotice("");
    }
  };

  const savePlan = async (plan) => {
    const latestIssue = dashboard?.latest_issue || "";
    const localRecord = {
      id: `ssq-${Date.now()}-${plan.strategy}-${plan.mode}`,
      saved_at: new Date().toISOString(),
      budget,
      strategy,
      latest_issue: latestIssue,
      plan,
    };
    try {
      const result = await saveSsqRecord({ budget, strategy, latestIssue, plan });
      setSavedPlans((items) => [result.record, ...items].slice(0, 100));
      await refreshReview();
      changeModule("history");
      setNotice("双色球方案已保存。");
    } catch (err) {
      const nextPlans = [localRecord, ...savedPlans].slice(0, 20);
      localStorage.setItem("cbgo_ssq_plans", JSON.stringify(nextPlans));
      setSavedPlans(nextPlans);
      changeModule("history");
      setNotice(`后端保存失败，双色球方案已保存到本地浏览器。${err?.message ? `原因：${err.message}` : ""}`);
    }
  };

  const importSyncedRecords = async (records) => {
    const signatures = new Set(savedPlans.map((record) => JSON.stringify(normalizeRecordPlan(record))));
    const incoming = records.filter((record) => {
      const plan = normalizeRecordPlan(record);
      const signature = JSON.stringify(plan);
      if (!plan?.mode || signatures.has(signature)) return false;
      signatures.add(signature);
      return true;
    });
    const saved = await Promise.all(incoming.map((record) => saveSsqRecord({
      budget: Number(record.budget || record.plan?.cost || 0),
      strategy: record.strategy || record.plan?.strategy || "balanced",
      latestIssue: record.latest_issue || record.plan?.recommended_issue || dashboard.latest_issue,
      plan: normalizeRecordPlan(record),
    })));
    if (saved.length) {
      const refreshed = await getSsqRecords();
      setSavedPlans(refreshed);
      await refreshReview();
    }
    return saved.length;
  };

  const deleteRecord = async (id) => {
    try {
      await deleteSsqRecord(id);
      setSavedPlans((items) => items.filter((record) => record.id !== id));
      await refreshReview();
      setNotice("双色球历史推荐记录已删除。");
    } catch (err) {
      setError(err.message);
    }
  };

  const importHistory = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setNotice("");
    try {
      const result = await importSsqHistory(file);
      await loadDashboard();
      await refreshDataStorage({ offset: 0, issue: "" });
      setNotice(`已导入 ${result.rows} 条 SSQ 开奖数据。`);
    } catch (err) {
      setError(err.message);
    } finally {
      event.target.value = "";
    }
  };

  const scoreRows = dashboard?.scoreboard || [];
  const isPublishedSnapshot = dashboard?.storage?.storage === "published_snapshot";
  const ssqView = dashboard ? {
    ...dashboard,
    score_table: scoreRows,
    capital_state: dashboard.capital,
    data_status: {
      ...(dashboard.storage || {}),
      source_label: dashboard.storage?.source_label || (isPublishedSnapshot ? "完整历史快照" : "SQLite 数据库"),
      is_sample: !isPublishedSnapshot && (dashboard.history_count || 0) <= 100,
      message: isPublishedSnapshot
        ? `当前分析基于发布时校验的 ${dashboard.history_count} 期双色球历史开奖数据。`
        : "当前双色球分析基于本地 SQLite 数据库。可通过 CSV 导入更新开奖数据。",
    },
    top_numbers: dashboard.top_front || [],
    recommended_amount: Math.max(...(dashboard.plans || []).map((plan) => plan.cost), 0),
    window: dashboard.trends?.window || windowSize,
  } : null;

  if (loading) {
    return <main className="loading"><RefreshCw className="spin" /> 正在计算 SSQ Module 数据...</main>;
  }

  if (error && !dashboard) {
    const fatalError = classifyError(error, "数据加载失败");
    return (
      <main className="loading">
        <ShieldAlert />
        <strong>{fatalError.title}</strong>
        <p>{fatalError.detail}</p>
        <button className="text-button" onClick={onBack} type="button">返回场景页</button>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <AppSidebar
        scenes={scenes}
        active="SSQ"
        activeModule={activeModule}
        onModuleChange={changeModule}
        onSelect={onSceneSelect}
      />

      <section className="workspace">
        <header className="workspace-topbar">
          <div>
            <Badge tone="live">双色球 SSQ</Badge>
            <h1>策维（Ceway）数字决策平台</h1>
            <p>Powered by CBGO Framework · SSQ Module　当前期号：{dashboard.latest_issue}　数据截至：{dashboard.storage?.latest_date || "-"}　推荐期号：{dashboard.recommended_issue || "下一期"}　<span className="status-dot" />运行状态：正常</p>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={onBack} type="button">
              <ArrowLeft size={16} />
              返回场景页
            </button>
            <Badge><Database size={13} /> {dashboard.history_count} 期历史记录</Badge>
            {!isPublishedSnapshot && (
              <label className="upload-button">
                <FileUp size={16} />
                导入CSV
                <input accept=".csv,text/csv" type="file" onChange={importHistory} />
              </label>
            )}
            <button className="icon-button" onClick={loadDashboard} title="刷新" type="button">
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        <ErrorNotice error={error} onRetry={loadDashboard} />
        {notice && <p className="notice">{notice}</p>}

        <section className="module-stage" aria-label={MODULE_TITLES[activeModule]}>
          {activeModule === "overview" && (
            <>
              <section className="stats" id="module-overview">
                <TopNumbersCard rows={scoreRows} />
                <StatCard icon={Gauge} label="当前下注状态" value={dashboard.capital.level} meta={`下一状态 ${dashboard.capital.next_level}`} />
                <StatCard icon={WalletCards} label="当前资金" value={`${dashboard.capital.balance} 元`} meta={`盈利 ${dashboard.capital.profit} 元`} />
                <StatCard icon={Coins} label="本期预算" value={`${budget} 元`} meta="进入投注方案生成或人工选号" />
              </section>
              <DataStatusPanel dataStatus={ssqView.data_status} onImport={importHistory} />
            </>
          )}

          {activeModule === "data" && (
            <BettingPlanPanel
              scene="SSQ"
              dashboard={dashboard}
              scoreRows={scoreRows}
              backScoreRows={dashboard.back_scoreboard}
              budget={budget}
              onBudgetChange={setBudget}
              generated={generated}
              onGenerated={setGenerated}
              onSave={savePlan}
              decisionContext={{ principal, periodCap, records: savedPlans, backtest, capital: dashboard.capital }}
            />
          )}

          {activeModule === "review" && <ReviewPanel review={review} onRefresh={refreshReview} />}
          {activeModule === "backtest" && <BacktestPanel backtest={backtest} onRefresh={refreshBacktest} strategy={strategy} onStrategyChange={setStrategy} />}
          {activeModule === "trends" && (
            <TrendPanel
              dashboard={ssqView}
              scoreRows={scoreRows}
              windowSize={windowSize}
              onWindowChange={(value) => {
                setWindowSize(value);
                loadDashboard({ window: value });
              }}
            />
          )}
          {activeModule === "score" && <ScoreTable rows={scoreRows} selectedNumbers={planFrontNumbers(generated)} />}
          {activeModule === "capital" && (
            <CapitalPanel
              capital={dashboard.capital}
              budget={budget}
              principal={principal}
              balance={balance}
              lastPrize={lastPrize}
              levelUnits={levelUnits}
              periodCap={periodCap}
              records={savedPlans}
              generated={generated}
              backtest={backtest}
              onBudgetChange={setBudget}
              onPrincipalChange={setPrincipal}
              onBalanceChange={setBalance}
              onLastPrizeChange={setLastPrize}
              onLevelChange={setLevelUnits}
              onPeriodCapChange={setPeriodCap}
              onApply={loadDashboard}
            />
          )}
          {activeModule === "history" && <HistoryRecords records={savedPlans} onDelete={deleteRecord} review={review} scene="SSQ" onImport={importSyncedRecords} />}
        </section>

        <footer className="disclaimer footer-note">
          <ShieldAlert size={16} />
          {dashboard.disclaimer} 彩票具有随机性，请理性娱乐，量力而行。
        </footer>
      </section>
    </main>
  );
}

function App() {
  const [scenes, setScenes] = useState([]);
  const [view, setView] = useState(() => new URLSearchParams(window.location.search).get("scene") || "scenes");

  const navigate = (nextView, module = "overview") => {
    const url = new URL(window.location.href);
    if (nextView === "scenes") {
      url.searchParams.delete("scene");
      url.searchParams.delete("module");
    } else {
      url.searchParams.set("scene", nextView.toLowerCase());
      url.searchParams.set("module", module);
    }
    window.history.pushState({}, "", url);
    setView(nextView.toLowerCase());
  };

  useEffect(() => {
    getScenes()
      .then(setScenes)
      .catch(() => {
        setScenes([
          { code: "DLT", name: "大乐透", enabled: true },
          { code: "SSQ", name: "双色球", enabled: true },
        ]);
      });
  }, []);

  useEffect(() => {
    const handlePopState = () => setView(new URLSearchParams(window.location.search).get("scene") || "scenes");
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  if (view === "dlt") {
    return <Dashboard scenes={scenes} onBack={() => navigate("scenes")} onSceneSelect={(code) => navigate(code)} />;
  }

  if (view === "ssq") {
    return <SsqDashboard scenes={scenes} onBack={() => navigate("scenes")} onSceneSelect={(code) => navigate(code)} />;
  }

  if (view !== "scenes") {
    const scene = scenes.find((item) => item.code.toLowerCase() === view);
    return <ModulePlaceholder scene={scene} scenes={scenes} onBack={() => navigate("scenes")} />;
  }

  return <SceneSelect scenes={scenes} onEnter={(code) => navigate(code)} />;
}

createRoot(document.getElementById("root")).render(<App />);
