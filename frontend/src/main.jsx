import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Clipboard,
  Coins,
  Database,
  ArrowLeft,
  FileStack,
  FileUp,
  Gauge,
  History,
  Home,
  LayoutDashboard,
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
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { generateDltPlan, getDltDashboard, getScenes, importDltHistory } from "./api";
import "./styles.css";

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
    value: "V1.2 Baseline",
    detail: "MVP 第一阶段完成",
    tone: "green",
  },
  {
    label: "下一阶段",
    value: "V1.3 Decision Pipeline",
    detail: "评分链路 · 预算生成 · 决策解释",
    tone: "purple",
  },
  {
    label: "更新日志",
    value: "MVP 盘点完成",
    detail: "新想法统一进入 Backlog",
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
    description: "历史回测、随机选号对照组、ROI、覆盖率和最大回撤分析。",
  },
  {
    version: "V2.0",
    title: "行为分析版",
    description: "AI 评分、Attention、论坛、公众号和外部公开数据进入统一评估。",
  },
];

function AppSidebar({ scenes, active = "DLT", onSelect }) {
  const navItems = [
    { label: "系统总览", icon: Home, active: true },
    { label: "走势分析", icon: TrendingUp },
    { label: "号码评分", icon: Table2 },
    { label: "组合生成", icon: FileStack },
    { label: "资金管理", icon: Coins },
    { label: "历史记录", icon: History, muted: true },
    { label: "系统设置", icon: Settings, muted: true },
  ];

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
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              className={`side-nav-item ${item.active ? "active" : ""}`}
              disabled={item.muted}
              key={item.label}
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
      action: "即将上线",
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
          <div className={`version-pill ${item.tone}`} key={item.version}>
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
            <p>Digital Decision Platform · Powered by CBGO Framework。当前以 v1.2 MVP 作为 Baseline，所有新想法统一进入 Backlog。</p>
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
          <Badge tone="live">v1.2 Baseline</Badge>
          <h2>冻结开发范围</h2>
          <p>当前版本只交付 DLT Module 的本地历史数据分析、预算控制和方案输出；新想法统一进入 Backlog。</p>
        </div>
        <div className="baseline-grid">
          <article>
            <h3>本版必须完成</h3>
            <ul>
              <li>场景中心与大乐透仪表盘</li>
              <li>冷热号、遗漏、奇偶比、大小比、和值</li>
              <li>号码评分、单式、胆拖、预算控制</li>
              <li>Anti-Martingale 资金状态机</li>
            </ul>
          </article>
          <article>
            <h3>本版不开发</h3>
            <ul>
              <li>AI、论坛、舆情、外部数据 API</li>
              <li>双色球正式支持与自动更新开奖</li>
              <li>历史回测平台与收益率验证</li>
              <li>任何超出 Baseline 的新增模块</li>
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

function TrendPanel({ dashboard }) {
  const missingByNumber = new Map(dashboard.trends.omissions.map((item) => [item.number, item.missing]));
  const hotFront = dashboard.trends.hot_front.slice(0, 35).map((item) => ({
    ...item,
    missing: missingByNumber.get(item.number) || 0,
  }));
  const sumValues = dashboard.trends.sum_values;
  const hottest = dashboard.trends.hot_front[0];
  const coldest = dashboard.trends.hot_front[dashboard.trends.hot_front.length - 1];
  const maxMissing = dashboard.trends.omissions.reduce((max, item) => item.missing > max.missing ? item : max, dashboard.trends.omissions[0]);

  return (
    <section className="panel wide">
      <div className="panel-title">
        <div>
          <h2>走势分析</h2>
          <p>最近 {dashboard.trends.window} 期历史开奖数据</p>
        </div>
        <Badge>Latest {dashboard.latest_issue}</Badge>
      </div>

      <div className="trend-tabs">
        <button className="active" type="button">冷热号</button>
        <button type="button">遗漏</button>
        <button type="button">奇偶比</button>
        <button type="button">大小比</button>
        <button type="button">和值</button>
      </div>

      <div className="trend-layout">
        <div className="chart-box primary-chart">
          <h3>冷热号分布（近100期）</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={hotFront}>
              <CartesianGrid stroke="rgba(134, 166, 194, 0.16)" vertical={false} />
              <XAxis dataKey="number" tickFormatter={(value) => `${value}`} />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Bar dataKey="missing" fill="#ef4d3c" radius={[3, 3, 0, 0]} />
              <Bar dataKey="count" fill="#1768d7" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
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
          <ResponsiveContainer width="100%" height={170}>
            <LineChart data={sumValues}>
              <CartesianGrid stroke="rgba(134, 166, 194, 0.16)" vertical={false} />
              <XAxis dataKey="issue" hide />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="value" stroke="#53a3ff" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

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

function ScoreTable({ rows }) {
  return (
    <section className="panel">
      <div className="panel-title">
        <div>
          <h2>号码评分</h2>
          <p>热度 0.4 · 遗漏 0.3 · 均衡 0.3</p>
        </div>
        <BarChart3 size={18} />
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
            </tr>
          </thead>
          <tbody>
            {rows.slice(0, 15).map((row) => (
              <tr key={row.number}>
                <td>{row.rank}</td>
                <td><strong>{String(row.number).padStart(2, "0")}</strong></td>
                <td>{row.heat_score}</td>
                <td>{row.missing_score}</td>
                <td>{row.balance_score}</td>
                <td className="score-hot">{row.total_score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function CapitalPanel({ capital }) {
  const curve = [
    200, 226, 241, 260, 210, 206, 155, 195, 252, 206,
    184, 268, 315, 374, 312, 246, 226, 302, 438, 332,
    296, 331, 286, 231, 292, 368, 432,
  ].map((value, index) => ({ issue: index + 1, value }));

  return (
    <section className="panel capital-panel">
      <div className="panel-title">
        <div>
          <h2>资金管理</h2>
          <p>Anti-Martingale：输了不加码，赢了才加码</p>
        </div>
        <Coins size={18} />
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
          <span>最大回撤</span>
          <strong>{capital.max_drawdown}%</strong>
        </div>
      </div>
      <div className="capital-chart">
        <h3>资金曲线（近50期）</h3>
        <ResponsiveContainer width="100%" height={170}>
          <LineChart data={curve}>
            <CartesianGrid stroke="rgba(134, 166, 194, 0.16)" vertical={false} />
            <XAxis dataKey="issue" />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#31d86b" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="state-machine">
        <span className={capital.level_units === 1 ? "active" : ""}>1注</span>
        <span className={capital.level_units === 2 ? "active" : ""}>2注</span>
        <span className={capital.level_units === 4 ? "active" : ""}>4注</span>
      </div>
    </section>
  );
}

function DataStatusPanel({ dataStatus, onImport }) {
  if (!dataStatus) return null;

  return (
    <section className={`data-status-panel ${dataStatus.is_sample ? "sample" : ""}`}>
      <div>
        <Badge>{dataStatus.source_label}</Badge>
        <h2>数据状态</h2>
        <p>{dataStatus.message}</p>
      </div>
      <dl>
        <div><dt>最新期号</dt><dd>{dataStatus.latest_issue || "-"}</dd></div>
        <div><dt>开奖日期</dt><dd>{dataStatus.latest_date || "-"}</dd></div>
        <div><dt>数据文件</dt><dd>{dataStatus.path}</dd></div>
      </dl>
      <label className="upload-button data-upload">
        <FileUp size={16} />
        导入最新CSV
        <input accept=".csv,text/csv" type="file" onChange={onImport} />
      </label>
    </section>
  );
}

function PlanCard({ plan, onSave }) {
  if (!plan) return null;

  const text = plan.mode === "dantuo"
    ? `前区胆码：${plan.front_dan_display.join(" ")}\n前区拖码：${plan.front_tuo_display.join(" ")}\n后区号码：${plan.back_display.join(" ")}\n共 ${plan.tickets} 注，费用 ${plan.cost} 元`
    : plan.items.map((item, index) => `${index + 1}. ${item.front_display.join(" ")} + ${item.back_display.join(" ")}`).join("\n");

  const copy = async () => {
    await navigator.clipboard.writeText(text);
  };

  return (
    <article className="plan-card">
      <div className="plan-head">
        <Badge tone={plan.mode === "dantuo" ? "live" : "default"}>
          {plan.mode === "dantuo" ? "胆拖" : "单式"}
        </Badge>
        <strong>{plan.cost} 元 · {plan.tickets} 注</strong>
      </div>
      {plan.mode === "dantuo" ? (
        <div className="number-groups">
          <div>
            <p>前区胆码（{plan.front_dan_display.length}个）</p>
            <div>{plan.front_dan_display.map((item) => <NumberBall key={item} tone="dan">{item}</NumberBall>)}</div>
          </div>
          <div>
            <p>前区拖码（{plan.front_tuo_display.length}个）</p>
            <div>{plan.front_tuo_display.map((item) => <NumberBall key={item}>{item}</NumberBall>)}</div>
          </div>
          <div>
            <p>后区（{plan.back_display.length}个）</p>
            <div>{plan.back_display.map((item) => <NumberBall key={item} tone="back">{item}</NumberBall>)}</div>
          </div>
        </div>
      ) : (
        <div className="single-list">
          {plan.items.slice(0, 8).map((item, index) => (
            <p key={`${item.front.join("-")}-${index}`}>{item.front_display.join(" ")} + {item.back_display.join(" ")}</p>
          ))}
        </div>
      )}
      <div className="plan-actions">
        <button className="icon-button text-button" onClick={copy} type="button">
          <Clipboard size={16} />
          复制方案
        </button>
        {onSave && (
          <button className="icon-button text-button" onClick={() => onSave(plan)} type="button">
            <Save size={16} />
            保存方案
          </button>
        )}
      </div>
    </article>
  );
}

function Dashboard({ scenes, onBack }) {
  const [budget, setBudget] = useState(20);
  const [lastPrize, setLastPrize] = useState(0);
  const [mode, setMode] = useState("auto");
  const [dashboard, setDashboard] = useState(null);
  const [generated, setGenerated] = useState(null);
  const [savedPlans, setSavedPlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const loadDashboard = async () => {
    setLoading(true);
    setError("");
    setNotice("");
    try {
      const data = await getDltDashboard({ budget, lastPrize });
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
    const stored = JSON.parse(localStorage.getItem("cbgo_saved_plans") || "[]");
    setSavedPlans(stored);
  }, []);

  const topNumbers = useMemo(() => {
    if (!dashboard) return "-";
    return dashboard.top_numbers.map((number) => String(number).padStart(2, "0")).join(" ");
  }, [dashboard]);

  const generate = async () => {
    setError("");
    setNotice("");
    try {
      const plan = await generateDltPlan({ budget, mode, lastPrize });
      setGenerated(plan);
    } catch (err) {
      setError(err.message);
    }
  };

  const savePlan = (plan) => {
    const nextPlans = [
      {
        ...plan,
        id: `${Date.now()}-${plan.mode}`,
        saved_at: new Date().toISOString(),
        budget,
        latest_issue: dashboard.latest_issue,
      },
      ...savedPlans,
    ].slice(0, 20);
    localStorage.setItem("cbgo_saved_plans", JSON.stringify(nextPlans));
    setSavedPlans(nextPlans);
    setNotice("方案已保存到本地浏览器。");
  };

  const importHistory = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setError("");
    setNotice("");
    try {
      const result = await importDltHistory(file);
      await loadDashboard();
      setNotice(`已导入 ${result.rows} 期历史开奖数据。`);
    } catch (err) {
      setError(err.message);
    } finally {
      event.target.value = "";
    }
  };

  if (loading) {
    return <main className="loading"><RefreshCw className="spin" /> 正在计算 DLT Module 数据...</main>;
  }

  if (error && !dashboard) {
    return (
      <main className="loading">
        <ShieldAlert />
        <p>{error}</p>
        <button className="text-button" onClick={onBack} type="button">返回</button>
      </main>
    );
  }

  return (
    <main className="app-shell">
      <AppSidebar scenes={scenes} active="DLT" onSelect={() => {}} onBack={onBack} />

      <section className="workspace">
        <header className="workspace-topbar">
          <div>
            <Badge tone="live">大乐透 DLT</Badge>
            <h1>策维（Ceway）数字决策平台</h1>
            <p>Powered by CBGO Framework · DLT Module　当前期号：{dashboard.latest_issue}　更新时间：2025-05-20 09:30:30　<span className="status-dot" />运行状态：正常</p>
          </div>
          <div className="topbar-actions">
            <button className="ghost-button" onClick={onBack} type="button">
              <ArrowLeft size={16} />
              返回场景页
            </button>
            <Badge><Database size={13} /> {dashboard.history_count} 期样本</Badge>
            <label className="upload-button">
              <FileUp size={16} />
              导入CSV
              <input accept=".csv,text/csv" type="file" onChange={importHistory} />
            </label>
            <button className="icon-button" onClick={loadDashboard} title="刷新" type="button">
              <RefreshCw size={18} />
            </button>
          </div>
        </header>

        <section className="control-panel">
          <label>
            本期预算
            <input min="2" step="2" type="number" value={budget} onChange={(event) => setBudget(Number(event.target.value))} />
          </label>
          <label>
            上期奖金
            <input min="0" step="5" type="number" value={lastPrize} onChange={(event) => setLastPrize(Number(event.target.value))} />
          </label>
          <label>
            生成模式
            <select value={mode} onChange={(event) => setMode(event.target.value)}>
              <option value="auto">自动</option>
              <option value="single">单式</option>
              <option value="dantuo">胆拖</option>
            </select>
          </label>
          <button className="primary-button" onClick={loadDashboard} type="button">
            <Activity size={16} />
            更新总览
          </button>
          <button className="primary-button strong" onClick={generate} type="button">
            <Play size={16} />
            生成方案
          </button>
        </section>

        <section className="stats">
          <StatCard icon={Sparkles} label="Top号码" value={topNumbers} meta="当前综合评分最高前区号码" />
          <StatCard icon={Gauge} label="当前下注状态" value={dashboard.capital_state.level} meta={`下一状态 ${dashboard.capital_state.next_level}`} />
          <StatCard icon={WalletCards} label="当前资金" value={`${dashboard.capital_state.balance} 元`} meta={`盈利 ${dashboard.capital_state.profit} 元`} />
          <StatCard icon={Coins} label="本期预算/金额" value={`${budget} / ${dashboard.recommended_amount} 元`} meta="推荐金额不超过预算" />
        </section>

        {error && <p className="error">{error}</p>}
        {notice && <p className="notice">{notice}</p>}
        <DataStatusPanel dataStatus={dashboard.data_status} onImport={importHistory} />

        <div className="module-grid">
          <TrendPanel dashboard={dashboard} />
          <ScoreTable rows={dashboard.score_table} />
          <section className="panel">
            <div className="panel-title">
              <div>
                <h2>组合生成</h2>
                <p>只保留费用小于等于预算的方案</p>
              </div>
              <LayoutDashboard size={18} />
            </div>
            {dashboard.plans[0]?.mode === "dantuo" && <PlanCard plan={dashboard.plans[0]} onSave={savePlan} />}
            <div className="plan-stack">
              {generated && <PlanCard plan={generated} onSave={savePlan} />}
              {dashboard.plans.slice(1).map((plan) => <PlanCard key={plan.mode} plan={plan} onSave={savePlan} />)}
            </div>
            <div className="saved-summary">
              <strong>已保存方案：{savedPlans.length}</strong>
              {savedPlans[0] && (
                <span>最近：{savedPlans[0].mode === "dantuo" ? "胆拖" : "单式"} · {savedPlans[0].cost} 元 · {savedPlans[0].tickets} 注</span>
              )}
            </div>
          </section>
          <CapitalPanel capital={dashboard.capital_state} />
        </div>

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
  const [view, setView] = useState("scenes");

  useEffect(() => {
    getScenes()
      .then(setScenes)
      .catch(() => {
        setScenes([
          { code: "DLT", name: "大乐透", enabled: true },
          { code: "SSQ", name: "双色球", enabled: false },
          { code: "K8", name: "快乐8", enabled: false },
          { code: "CUSTOM", name: "自定义分析", enabled: false },
        ]);
      });
  }, []);

  if (view === "dlt") {
    return <Dashboard scenes={scenes} onBack={() => setView("scenes")} />;
  }

  if (view !== "scenes") {
    const scene = scenes.find((item) => item.code.toLowerCase() === view);
    return <ModulePlaceholder scene={scene} scenes={scenes} onBack={() => setView("scenes")} />;
  }

  return <SceneSelect scenes={scenes} onEnter={(code) => setView(code.toLowerCase())} />;
}

createRoot(document.getElementById("root")).render(<App />);
