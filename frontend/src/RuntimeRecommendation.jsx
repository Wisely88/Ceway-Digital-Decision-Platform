import React, { useEffect, useMemo, useState } from "react";
import { Check, Clipboard, RefreshCw, ShieldCheck } from "lucide-react";
import { getRuntimeRecommendation } from "./api";
import "./runtimeRecommendation.css";


function numbers(values = []) {
  return values.map((value) => String(value).padStart(2, "0")).join(" ");
}


function copyFallback(text) {
  const area = document.createElement("textarea");
  area.value = text;
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  document.execCommand("copy");
  area.remove();
}


async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  copyFallback(text);
}


function TicketNumbers({ ticket, scene }) {
  const primaryName = scene === "DLT" ? "前区" : "红球";
  const secondaryName = scene === "DLT" ? "后区" : "蓝球";
  return (
    <div className="runtime-ticket-lines">
      <p>
        <span>{primaryName}</span>
        {ticket.primary_dan?.length > 0 && <><b>胆 {numbers(ticket.primary_dan)}</b><i>｜</i></>}
        <b>拖 {numbers(ticket.primary_tuo)}</b>
      </p>
      <p>
        <span>{secondaryName}</span>
        {ticket.secondary_dan?.length > 0 && <><b>胆 {numbers(ticket.secondary_dan)}</b><i>｜</i></>}
        <b>拖 {numbers(ticket.secondary_tuo)}</b>
      </p>
    </div>
  );
}


function RuntimeRecommendation({ scene }) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedRank, setSelectedRank] = useState(1);
  const [notice, setNotice] = useState("");

  const load = async (refresh = false) => {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const result = await getRuntimeRecommendation({ game: scene, refresh, minCost: 18, maxCost: 24 });
      setPayload(result);
      setSelectedRank(1);
    } catch (err) {
      setError(err.message || "推荐后台暂不可用");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load(false);
  }, [scene]);

  const selected = payload?.recommendations?.[selectedRank - 1];
  const ticket = payload?.ticket;
  const components = ticket?.components || (ticket ? [ticket] : []);
  const pick = payload?.budget_pick;
  const primaryName = scene === "DLT" ? "前区" : "红球";
  const secondaryName = scene === "DLT" ? "后区" : "蓝球";
  const statusLabel = payload?.runtime?.mode === "frozen" ? "正式冻结" : "上午预览";

  const copyCandidate = async () => {
    if (!selected) return;
    await copyText(`${payload.game_name} ${payload.target_issue}期 第${selectedRank}组\n${selected.text}`);
    setNotice(`第 ${selectedRank} 组单注已复制。`);
  };

  const copyPick = async () => {
    if (!pick) return;
    const text = [
      `${payload.game_name} ${payload.target_issue}期 精选胆拖`,
      `${primaryName}胆：${numbers(pick.primary_dan)}`,
      `${primaryName}拖：${numbers(pick.primary_tuo)}`,
      `${secondaryName}：${numbers(pick.secondary_tuo)}`,
      `${pick.notes}注，共${pick.cost}元`,
    ].join("\n");
    await copyText(text);
    setNotice(`${pick.cost} 元精选胆拖已复制。`);
  };

  const coverage = useMemo(() => {
    if (!ticket) return "-";
    return `${ticket.covers_top || 0}/${ticket.top_size || payload?.recommendations?.length || 0}`;
  }, [payload, ticket]);

  if (loading) {
    return <section className="runtime-loading"><RefreshCw className="spin" />正在读取本期推荐...</section>;
  }

  if (error) {
    return (
      <section className="runtime-error">
        <strong>推荐后台暂时没有连上</strong>
        <p>{error}</p>
        <button className="primary-button" onClick={() => load(false)} type="button">重试</button>
      </section>
    );
  }

  return (
    <div className="runtime-page">
      <section className="runtime-heading">
        <div>
          <span className={`runtime-state ${payload.runtime.mode}`}>{statusLabel}</span>
          <h2>{payload.game_name}第 {payload.target_issue} 期</h2>
          <p>历史截止 {payload.history_cutoff_issue} · 共 {payload.history_draws} 期 · 最新开奖 {payload.runtime.latest_date}</p>
        </div>
        <button className="ghost-button" onClick={() => load(true)} type="button">
          <RefreshCw size={16} />
          刷新状态
        </button>
      </section>

      <section className="runtime-summary" aria-label="推荐摘要">
        <div><span>候选</span><strong>{payload.recommendations.length} 组</strong></div>
        <div><span>胆拖覆盖</span><strong>{coverage}</strong></div>
        <div><span>精选预算</span><strong>{pick ? `${pick.cost} 元` : "暂无"}</strong></div>
        <div><span>推送状态</span><strong>{payload.runtime.pushed ? "已推送" : "待正式推送"}</strong></div>
      </section>

      {pick && (
        <section className="runtime-pick">
          <div className="runtime-section-title">
            <div>
              <span>建议先看这一组</span>
              <h3>{pick.cost} 元精选胆拖</h3>
            </div>
            <button className="primary-button" onClick={copyPick} type="button"><Clipboard size={16} />复制</button>
          </div>
          <TicketNumbers ticket={pick} scene={scene} />
          <p className="runtime-pick-meta">{pick.notes} 注 · 来源第 {pick.source_rank} 组 · 覆盖候选 {pick.covered_indexes.join("、") || "1"}</p>
        </section>
      )}

      <section className="runtime-candidates">
        <div className="runtime-section-title">
          <div><span>按综合分排列</span><h3>18 组单注候选</h3></div>
          <button className="ghost-button" onClick={copyCandidate} type="button"><Clipboard size={16} />复制所选</button>
        </div>
        <div className="runtime-candidate-grid">
          {payload.recommendations.map((candidate, index) => (
            <button
              className={selectedRank === index + 1 ? "selected" : ""}
              key={candidate.text}
              onClick={() => setSelectedRank(index + 1)}
              type="button"
            >
              <span>{String(index + 1).padStart(2, "0")}</span>
              <b>{numbers(candidate.primary)}</b>
              <i>+</i>
              <em>{numbers(candidate.secondary)}</em>
              {selectedRank === index + 1 && <Check size={15} />}
            </button>
          ))}
        </div>
      </section>

      <details className="runtime-coverage">
        <summary>
          <span><ShieldCheck size={18} />查看完整胆拖覆盖</span>
          <b>{components.length} 组 · {ticket.notes} 注 · {ticket.cost} 元</b>
        </summary>
        <p className="runtime-coverage-note">完整覆盖用于核对推荐池，按需挑选，不需要全部购买。</p>
        <div className="runtime-component-list">
          {components.map((component, index) => (
            <article key={`${index}-${component.covered_indexes?.join("-")}`}>
              <header><strong>{String(index + 1).padStart(2, "0")}</strong><span>覆盖 {component.covered_indexes?.join("、") || "-"}</span><b>{component.notes}注 · {component.cost}元</b></header>
              <TicketNumbers ticket={component} scene={scene} />
            </article>
          ))}
        </div>
      </details>

      {notice && <p className="runtime-notice">{notice}</p>}
      <p className="runtime-caveat">历史统计只用于整理选择，不代表未来中奖概率。请按自己的预算理性参与。</p>
    </div>
  );
}


export default RuntimeRecommendation;
