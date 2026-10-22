import React, { useMemo, useState } from "react";
import { Download, FlaskConical, Play, RefreshCw } from "lucide-react";
import { analyzeSsqLabCollisions, generateSsqLabModel, generateSsqLabRandom } from "./api";
import "./dltLab.css";


const TABS = [
  ["model", "综合模型"],
  ["random", "随机对照"],
  ["collision", "历史碰撞"],
];


function nextIssue(issue) {
  if (!issue || !/^\d+$/.test(issue)) return "";
  return String(Number(issue) + 1).padStart(issue.length, "0");
}


function BallSet({ values, tone = "front" }) {
  return <span className="lab-ball-set">{values.map((value) => <i className={`lab-ball ${tone}`} key={value}>{String(value).padStart(2, "0")}</i>)}</span>;
}


function CollisionMatrix({ matrix }) {
  if (!matrix) return null;
  return (
    <div className="lab-matrix-wrap">
      <table className="lab-matrix">
        <thead><tr><th>红球命中</th><th>蓝球 0</th><th>蓝球 1</th></tr></thead>
        <tbody>{matrix.map((row, frontHits) => <tr key={frontHits}><th>{frontHits}</th>{row.map((count, backHits) => <td key={backHits}>{count}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}


function exportTickets(result) {
  const rows = ["序号,红球,蓝球,来源,目标期,历史截止期"];
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
  link.download = `ceway-ssq-${result?.target_issue || "collision"}.csv`;
  link.click();
  URL.revokeObjectURL(link.href);
}


function ResultPanel({ result }) {
  const [expanded, setExpanded] = useState("");
  if (!result) return null;
  return (
    <section className="lab-result">
      <header><div><strong>{result.mode === "model" ? "综合模型结果" : result.mode === "random" ? "随机对照结果" : "历史碰撞结果"}</strong><span>{result.history?.draw_count || 0} 期历史 · {result.total_bets || 0} 注</span></div><button className="ghost-button" onClick={() => exportTickets(result)} type="button"><Download size={15} />导出 CSV</button></header>
      <div className="lab-ticket-table-wrap">
        <table className="lab-ticket-table">
          <thead><tr><th>#</th><th>红球</th><th>蓝球</th><th>历史最高碰撞</th><th>综合分</th><th /></tr></thead>
          <tbody>{(result.tickets || []).map((ticket, index) => {
            const key = `${ticket.front.join("-")}-${ticket.back.join("-")}-${index}`;
            return <React.Fragment key={key}>
              <tr><td>{index + 1}</td><td><BallSet values={ticket.front} /></td><td><BallSet values={ticket.back} tone="back" /></td><td>{ticket.collision?.max_total_hits ?? "-"} 位</td><td>{ticket.score_breakdown?.secondary ?? "-"}</td><td><button className="lab-link" onClick={() => setExpanded(expanded === key ? "" : key)} type="button">{expanded === key ? "收起" : "碰撞详情"}</button></td></tr>
              {expanded === key && <tr className="lab-expanded"><td colSpan="6"><div className="lab-profile"><div className="lab-hit-grid">{ticket.collision.n_total_hits.map((count, hit) => <article key={hit}><b>N{hit}</b><span>{count} 次</span></article>)}</div><CollisionMatrix matrix={ticket.collision.n_front_back} /></div></td></tr>}
            </React.Fragment>;
          })}</tbody>
        </table>
      </div>
      {result.aggregate && <section className="lab-aggregate"><div><strong>整批碰撞汇总</strong><span>{result.aggregate.candidate_count} 组候选</span></div><div className="lab-hit-grid">{result.aggregate.m_total_hits.map((value, index) => <article key={index}><b>N{index}</b><span>M {value}</span><span>U {result.aggregate.u_total_hits[index]}</span></article>)}</div><details><summary>查看红球/蓝球碰撞矩阵</summary><div className="lab-dual-matrix"><div><h4>M_ab 组合期次对</h4><CollisionMatrix matrix={result.aggregate.m_front_back} /></div><div><h4>U_ab 不同候选数</h4><CollisionMatrix matrix={result.aggregate.u_front_back} /></div></div></details></section>}
      <p className="lab-disclaimer">{result.disclaimer}</p>
    </section>
  );
}


export default function SsqLab({ latestIssue }) {
  const targetIssue = useMemo(() => nextIssue(latestIssue), [latestIssue]);
  const [tab, setTab] = useState("model");
  const [model, setModel] = useState({ output: 8, frontPool: 10, backPool: 4, window: 120 });
  const [randomCount, setRandomCount] = useState(8);
  const [collisionText, setCollisionText] = useState("03 07 12 18 24 31 + 08");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const execute = async (action, success) => {
    setBusy(true); setError(""); setNotice("");
    try { setResult(await action()); setNotice(success); } catch (cause) { setError(cause.message); } finally { setBusy(false); }
  };

  const parseTickets = () => collisionText.split(/\n+/).filter(Boolean).map((line) => {
    const [frontText, backText] = line.split("+");
    if (!backText) throw new Error("每行请使用“6个红球 + 1个蓝球”的格式。");
    return { front: frontText.trim().split(/[\s,，]+/).map(Number), back: backText.trim().split(/[\s,，]+/).map(Number) };
  });

  return (
    <section className="dlt-lab">
      <header className="lab-heading"><div><span><FlaskConical size={18} />统计实验模块</span><h2>双色球实验室</h2><p>按 6 红 + 1 蓝完整组合进行历史碰撞、模型排序和随机对照。</p></div><div className="lab-context"><span>目标期</span><strong>{targetIssue || "-"}</strong><small>历史截止 {latestIssue || "-"}</small></div></header>
      <div className="lab-tabs" role="tablist">{TABS.map(([key, label]) => <button aria-selected={tab === key} className={tab === key ? "active" : ""} key={key} onClick={() => { setTab(key); setError(""); setNotice(""); }} role="tab" type="button">{label}</button>)}</div>
      {error && <p className="lab-message error">{error}</p>}
      {notice && <p className="lab-message success">{notice}</p>}

      {tab === "model" && <section className="lab-workbench"><div className="lab-form-grid">
        <label>历史窗口<input min="20" max="5000" type="number" value={model.window} onChange={(event) => setModel({ ...model, window: Number(event.target.value) })} /></label>
        <label>红球候选池<input min="6" max="12" type="number" value={model.frontPool} onChange={(event) => setModel({ ...model, frontPool: Number(event.target.value) })} /></label>
        <label>蓝球候选池<input min="1" max="8" type="number" value={model.backPool} onChange={(event) => setModel({ ...model, backPool: Number(event.target.value) })} /></label>
        <label>输出注数<input min="1" max="50" type="number" value={model.output} onChange={(event) => setModel({ ...model, output: Number(event.target.value) })} /></label>
        <button className="primary-button" disabled={busy || !targetIssue} onClick={() => execute(() => generateSsqLabModel({ target_issue: targetIssue, history_cutoff_issue: latestIssue, history_window: { mode: "last_N", count: model.window }, front_pool_size: model.frontPool, back_pool_size: model.backPool, output_count: model.output }), "模型运行完成，结果已按完整组合历史碰撞排序。") } type="button">{busy ? <RefreshCw className="spin" size={16} /> : <Play size={16} />}运行模型</button>
      </div></section>}

      {tab === "random" && <section className="lab-workbench"><div className="lab-form-grid"><label>随机注数<input min="1" max="200" type="number" value={randomCount} onChange={(event) => setRandomCount(Number(event.target.value))} /></label><button className="primary-button" disabled={busy || !targetIssue} onClick={() => execute(() => generateSsqLabRandom({ target_issue: targetIssue, history_cutoff_issue: latestIssue, count: randomCount }), "安全随机对照已生成，并完成全历史碰撞。") } type="button"><Play size={16} />生成随机对照</button></div></section>}

      {tab === "collision" && <section className="lab-workbench lab-collision-input"><label>每行一组完整号码<textarea rows="5" value={collisionText} onChange={(event) => setCollisionText(event.target.value)} /></label><button className="primary-button" disabled={busy || !latestIssue} onClick={() => execute(() => analyzeSsqLabCollisions({ history_cutoff_issue: latestIssue, window: { mode: "all_history" }, tickets: parseTickets() }), "历史碰撞分析完成。") } type="button"><Play size={16} />逐期碰撞分析</button></section>}
      <ResultPanel result={result} />
    </section>
  );
}
