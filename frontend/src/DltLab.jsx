import React, { useEffect, useMemo, useState } from "react";
import { Copy, Download, FlaskConical, LockKeyhole, Play, RefreshCw, Snowflake } from "lucide-react";
import {
  analyzeDltLabCollisions,
  cloneDltLabRun,
  freezeDltLabRun,
  generateDltLabModel,
  generateDltLabPackage,
  generateDltLabRandom,
  getDltLabRuns,
  settleDltLabRun,
} from "./api";
import "./dltLab.css";

const TABS = [
  ["model", "模型选号"],
  ["random", "随机选号"],
  ["package", "预算套餐"],
  ["collision", "历史碰撞"],
  ["review", "冻结复盘"],
];

const STATUS_LABELS = { draft: "草稿", frozen: "已冻结", settled: "已复盘" };
const MODE_LABELS = { model: "综合模型", scarcity: "碰撞稀缺", random: "纯随机", package: "预算套餐" };

function nextIssue(issue) {
  if (!issue || !/^\d+$/.test(issue)) return "";
  return String(Number(issue) + 1).padStart(issue.length, "0");
}

function modelHistoryWindow(model) {
  if (model.windowMode === "all_history") return { mode: "all_history" };
  if (model.windowMode === "custom") {
    return { mode: "custom", start_issue: model.startIssue, end_issue: model.endIssue };
  }
  return { mode: "last_N", count: model.window };
}

function BallSet({ values, tone = "front" }) {
  return <span className="lab-ball-set">{values.map((value) => <i className={`lab-ball ${tone}`} key={value}>{String(value).padStart(2, "0")}</i>)}</span>;
}

function CollisionMatrix({ matrix }) {
  if (!matrix) return null;
  return (
    <div className="lab-matrix-wrap">
      <table className="lab-matrix">
        <thead><tr><th>前区命中</th><th>后区 0</th><th>后区 1</th><th>后区 2</th></tr></thead>
        <tbody>{matrix.map((row, frontHits) => (
          <tr key={frontHits}><th>{frontHits}</th>{row.map((count, backHits) => <td key={backHits}>{count}</td>)}</tr>
        ))}</tbody>
      </table>
    </div>
  );
}

function Aggregate({ aggregate }) {
  if (!aggregate) return null;
  return (
    <section className="lab-aggregate">
      <div><strong>整批碰撞汇总</strong><span>{aggregate.candidate_count || 0} 组候选</span></div>
      <div className="lab-hit-grid">
        {aggregate.m_total_hits.map((value, index) => (
          <article key={index}><b>N{index}</b><span>M {value}</span><span>U {aggregate.u_total_hits[index]}</span></article>
        ))}
      </div>
      <details><summary>查看整批 M_ab / U_ab 矩阵</summary>
        <div className="lab-dual-matrix"><div><h4>M_ab 组合期次对</h4><CollisionMatrix matrix={aggregate.m_front_back} /></div><div><h4>U_ab 不同候选数</h4><CollisionMatrix matrix={aggregate.u_front_back} /></div></div>
      </details>
    </section>
  );
}

function TicketTable({ tickets = [] }) {
  const [expanded, setExpanded] = useState("");
  return (
    <div className="lab-ticket-table-wrap">
      <table className="lab-ticket-table">
        <thead><tr><th>#</th><th>前区</th><th>后区</th><th>历史最高碰撞</th><th>次评分</th><th /></tr></thead>
        <tbody>{tickets.map((ticket, index) => {
          const key = ticket.id || `${ticket.front.join("-")}-${ticket.back.join("-")}-${index}`;
          const collision = ticket.collision;
          return (
            <React.Fragment key={key}>
              <tr>
                <td>{ticket.ordinal || index + 1}</td>
                <td><BallSet values={ticket.front} /></td>
                <td><BallSet values={ticket.back} tone="back" /></td>
                <td>{collision ? `${collision.max_total_hits} 位` : "-"}</td>
                <td>{ticket.score_breakdown?.secondary?.toFixed?.(3) ?? "-"}</td>
                <td>{collision && <button className="lab-link" onClick={() => setExpanded(expanded === key ? "" : key)} type="button">{expanded === key ? "收起" : "碰撞详情"}</button>}</td>
              </tr>
              {expanded === key && collision && <tr className="lab-expanded"><td colSpan="6">
                <div className="lab-profile"><div className="lab-hit-grid">{collision.n_total_hits.map((count, hit) => <article key={hit}><b>N{hit}</b><span>{count} 次</span></article>)}</div><CollisionMatrix matrix={collision.n_front_back} /></div>
              </td></tr>}
            </React.Fragment>
          );
        })}</tbody>
      </table>
    </div>
  );
}

function exportTickets(result) {
  const rows = ["序号,前区,后区,来源,目标期,历史截止期"];
  (result?.tickets || []).forEach((ticket, index) => rows.push([
    index + 1,
    ticket.front.map((value) => String(value).padStart(2, "0")).join(" "),
    ticket.back.map((value) => String(value).padStart(2, "0")).join(" "),
    result.mode || "collision",
    result.target_issue || "",
    result.history_cutoff_issue || "",
  ].join(",")));
  const link = document.createElement("a");
  link.href = URL.createObjectURL(new Blob([`\ufeff${rows.join("\n")}`], { type: "text/csv;charset=utf-8" }));
  link.download = `ceway-dlt-${result?.target_issue || "collision"}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}

function ResultPanel({ result }) {
  if (!result) return null;
  return (
    <section className="lab-result">
      <header><div><strong>{MODE_LABELS[result.mode] || "碰撞分析结果"}</strong><span>{result.id ? `运行 ${result.id.slice(-8)}` : "即时分析"}</span></div><button className="ghost-button" onClick={() => exportTickets(result)} type="button"><Download size={15} />导出 CSV</button></header>
      {result.id && <div className="lab-run-facts"><span>状态：{STATUS_LABELS[result.status]}</span><span>目标期：{result.target_issue}</span><span>数据截止：{result.history_cutoff_issue || "不使用历史"}</span><span>{result.total_bets} 注 / {result.total_cost_yuan} 元</span></div>}
      <TicketTable tickets={result.tickets} />
      <Aggregate aggregate={result.aggregate} />
      <p className="lab-disclaimer">{result.disclaimer || "历史碰撞和结构统计只描述过去，不代表未来开奖概率。"}</p>
    </section>
  );
}

function RunsPanel({ runs, busy, onAction }) {
  if (!runs.length) return <div className="lab-empty">还没有实验运行。先在前四个页签生成结果，系统会保存为草稿。</div>;
  return <div className="lab-run-list">{runs.map((run) => (
    <article key={run.id}>
      <div className="lab-run-main"><span className={`lab-status ${run.status}`}>{STATUS_LABELS[run.status]}</span><div><strong>{MODE_LABELS[run.mode] || run.mode} · 第 {run.target_issue} 期</strong><span>版本 {run.version} · {run.total_bets} 注 · {run.total_cost_yuan} 元</span></div></div>
      <div className="lab-run-actions">
        {run.status === "draft" && <button disabled={busy} onClick={() => onAction("freeze", run.id)} type="button"><LockKeyhole size={15} />冻结</button>}
        {run.status !== "draft" && <button disabled={busy} onClick={() => onAction("clone", run.id)} type="button"><Copy size={15} />复制新版本</button>}
        {run.status === "frozen" && <button disabled={busy} onClick={() => onAction("settle", run.id)} type="button"><Play size={15} />开奖复盘</button>}
      </div>
      {run.freeze && <p className="lab-hash"><Snowflake size={14} /> SHA-256：{run.freeze.sha256}</p>}
      {run.settlement && <div className="lab-settlement"><strong>实际开奖</strong><BallSet values={run.settlement.actual.front} /><BallSet values={run.settlement.actual.back} tone="back" /><span>最佳命中 {run.settlement.best?.hit_label || "-"}，号码池覆盖 {run.settlement.pool_coverage.front_hits}+{run.settlement.pool_coverage.back_hits}</span></div>}
    </article>
  ))}</div>;
}

export default function DltLab({ latestIssue }) {
  const targetIssue = useMemo(() => nextIssue(latestIssue), [latestIssue]);
  const [tab, setTab] = useState("model");
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [model, setModel] = useState({ output: 5, frontPool: 10, backPool: 4, windowMode: "last_N", window: 120, startIssue: "", endIssue: "", ranking: "model" });
  const [random, setRandom] = useState({ count: 5, type: "single", addon: false, multiplier: 1 });
  const [budget, setBudget] = useState({ amount: 50, template: "mixed", source: "random", addon: false, multiplier: 1 });
  const [collisionText, setCollisionText] = useState("03 07 12 14 26 + 05 11");

  const refreshRuns = async () => {
    try { setRuns((await getDltLabRuns()).items || []); } catch (cause) { setError(cause.message); }
  };
  useEffect(() => { refreshRuns(); }, []);

  const execute = async (action, success) => {
    setBusy(true); setError(""); setNotice("");
    try {
      const payload = await action();
      setResult(payload);
      setNotice(success);
      await refreshRuns();
    } catch (cause) { setError(cause.message); } finally { setBusy(false); }
  };

  const parseTickets = () => collisionText.split(/\n+/).filter(Boolean).map((line) => {
    const [frontText, backText] = line.split("+");
    if (!backText) throw new Error("每行请使用“5个前区 + 2个后区”的格式。");
    return { front: frontText.trim().split(/[\s,，]+/).map(Number), back: backText.trim().split(/[\s,，]+/).map(Number) };
  });

  const actOnRun = async (action, id) => execute(
    () => action === "freeze" ? freezeDltLabRun(id) : action === "clone" ? cloneDltLabRun(id) : settleDltLabRun(id),
    action === "freeze" ? "运行已冻结，号码、参数和碰撞指纹不可再原地修改。" : action === "clone" ? "已复制为可编辑的新版本。" : "开奖复盘完成。",
  );

  return (
    <section className="dlt-lab">
      <header className="lab-heading"><div><span><FlaskConical size={18} />统计实验模块</span><h2>大乐透实验室</h2><p>完整组合逐期碰撞、预算表达与冻结复盘。它描述历史，不预测未来。</p></div><div className="lab-context"><span>目标期</span><strong>{targetIssue || "-"}</strong><small>历史截止 {latestIssue || "-"}</small></div></header>
      <div className="lab-tabs" role="tablist">{TABS.map(([key, label]) => <button aria-selected={tab === key} className={tab === key ? "active" : ""} key={key} onClick={() => { setTab(key); setError(""); setNotice(""); }} role="tab" type="button">{label}</button>)}</div>
      {error && <p className="lab-message error">{error}</p>}
      {notice && <p className="lab-message success">{notice}</p>}

      {tab === "model" && <section className="lab-workbench"><div className="lab-form-grid">
        <label>排序模型<select value={model.ranking} onChange={(event) => setModel({ ...model, ranking: event.target.value })}><option value="model">综合模型</option><option value="scarcity">仅碰撞稀缺</option></select></label>
        <label>历史窗口<select value={model.windowMode} onChange={(event) => setModel({ ...model, windowMode: event.target.value })}><option value="all_history">全部历史</option><option value="last_N">最近 N 期</option><option value="custom">自定义期号</option></select></label>
        {model.windowMode === "last_N" && <label>最近历史期数<input min="1" max="5000" type="number" value={model.window} onChange={(event) => setModel({ ...model, window: Number(event.target.value) })} /></label>}
        {model.windowMode === "custom" && <><label>起始期号<input placeholder="例如 24001" value={model.startIssue} onChange={(event) => setModel({ ...model, startIssue: event.target.value.trim() })} /></label><label>结束期号<input placeholder={latestIssue || "截止期"} value={model.endIssue} onChange={(event) => setModel({ ...model, endIssue: event.target.value.trim() })} /></label></>}
        <label>前区候选池<input min="5" max="18" type="number" value={model.frontPool} onChange={(event) => setModel({ ...model, frontPool: Number(event.target.value) })} /></label>
        <label>后区候选池<input min="2" max="8" type="number" value={model.backPool} onChange={(event) => setModel({ ...model, backPool: Number(event.target.value) })} /></label>
        <label>输出注数<input min="1" max="100" type="number" value={model.output} onChange={(event) => setModel({ ...model, output: Number(event.target.value) })} /></label>
        <button className="primary-button" disabled={busy || !targetIssue || (model.windowMode === "custom" && (!model.startIssue || !model.endIssue))} onClick={() => execute(() => generateDltLabModel({ target_issue: targetIssue, history_cutoff_issue: latestIssue, history_window: modelHistoryWindow(model), front_pool_size: model.frontPool, back_pool_size: model.backPool, output_count: model.output, ranking_mode: model.ranking }), "模型运行已保存为草稿，可在冻结复盘页确认版本。") } type="button">{busy ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}运行模型</button>
      </div></section>}

      {tab === "random" && <section className="lab-workbench"><div className="lab-form-grid">
        <label>投注表达<select value={random.type} onChange={(event) => setRandom({ ...random, type: event.target.value })}><option value="single">单式</option><option value="front_compound">前区复式</option><option value="back_compound">后区复式</option><option value="double_compound">双区复式</option><option value="front_dantuo">前区胆拖</option><option value="double_dantuo">双区胆拖</option></select></label>
        <label>生成组数<input min="1" max="100" type="number" value={random.count} onChange={(event) => setRandom({ ...random, count: Number(event.target.value) })} /></label>
        <label>倍数<input min="1" max="99" type="number" value={random.multiplier} onChange={(event) => setRandom({ ...random, multiplier: Number(event.target.value) })} /></label>
        <label className="lab-check"><input checked={random.addon} onChange={(event) => setRandom({ ...random, addon: event.target.checked })} type="checkbox" />追加投注</label>
        <button className="primary-button" disabled={busy || !targetIssue} onClick={() => execute(() => generateDltLabRandom({ target_issue: targetIssue, history_cutoff_issue: latestIssue, count: random.count, bet_expression: { type: random.type }, addon: random.addon, multiplier: random.multiplier }), "安全随机结果已保存为草稿。") } type="button"><Play size={16} />安全随机</button>
      </div></section>}

      {tab === "package" && <section className="lab-workbench"><div className="lab-form-grid">
        <label>预算<input min="2" type="number" value={budget.amount} onChange={(event) => setBudget({ ...budget, amount: Number(event.target.value) })} /></label>
        <label>预算模板<select value={budget.template} onChange={(event) => setBudget({ ...budget, template: event.target.value })}><option value="dispersed_singles">分散单式</option><option value="addon_singles">追加单式</option><option value="small_compound">小复式</option><option value="dantuo">胆拖</option><option value="mixed">混合</option></select></label>
        <label>号码来源<select value={budget.source} onChange={(event) => setBudget({ ...budget, source: event.target.value })}><option value="random">纯随机</option><option value="model">综合模型</option><option value="scarcity">碰撞稀缺</option><option value="mixed">混合</option></select></label>
        <label>倍数<input min="1" max="99" type="number" value={budget.multiplier} onChange={(event) => setBudget({ ...budget, multiplier: Number(event.target.value) })} /></label>
        <label className="lab-check"><input checked={budget.addon} onChange={(event) => setBudget({ ...budget, addon: event.target.checked })} type="checkbox" />追加投注</label>
        <button className="primary-button" disabled={busy || !targetIssue} onClick={() => execute(() => generateDltLabPackage({ target_issue: targetIssue, history_cutoff_issue: latestIssue, history_window: { mode: "last_N", count: 120 }, budget_yuan: budget.amount, template: budget.template, source: budget.source, addon: budget.addon, multiplier: budget.multiplier }), "预算模板已按真实展开注数保存为草稿。") } type="button"><Play size={16} />生成预算组合</button>
      </div></section>}

      {tab === "collision" && <section className="lab-workbench lab-collision-input"><label>每行一组完整号码<textarea rows="5" value={collisionText} onChange={(event) => setCollisionText(event.target.value)} /></label><button className="primary-button" disabled={busy || !latestIssue} onClick={() => execute(() => analyzeDltLabCollisions({ history_cutoff_issue: latestIssue, window: { mode: "all_history" }, tickets: parseTickets() }), "历史碰撞分析完成。") } type="button"><Play size={16} />逐期碰撞分析</button></section>}
      {tab === "review" && <section className="lab-workbench"><div className="lab-section-head"><div><h3>运行版本</h3><p>冻结后不可原地修改；需要调整时复制为新版本。</p></div><button className="ghost-button" onClick={refreshRuns} type="button"><RefreshCw size={15} />刷新</button></div><RunsPanel busy={busy} onAction={actOnRun} runs={runs} /></section>}
      {tab !== "review" && <ResultPanel result={result} />}
    </section>
  );
}
