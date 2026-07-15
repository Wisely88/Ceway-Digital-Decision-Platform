import React from "react";
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

const gridStroke = "rgba(134, 166, 194, 0.16)";

function TrendTooltip({ active, payload, scoreRows = [] }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const score = scoreRows.find((item) => Number(item.number) === Number(row.number));
  return (
    <div className="chart-tooltip">
      <strong>{String(row.number).padStart(2, "0")}</strong>
      {row.count !== undefined && <span>出现次数：{row.count}</span>}
      {row.missing !== undefined && <span>当前遗漏：{row.missing} 期</span>}
      {score && <span>综合评分：{score.total_score}</span>}
      {score && <span>排名：{score.rank}</span>}
    </div>
  );
}

export function TrendBarChart({ data, mode = "hot", scoreRows = [] }) {
  return (
    <ResponsiveContainer width="100%" height={mode === "hot" ? 250 : 300}>
      <BarChart data={data}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey={mode === "ratio" ? "ratio" : "number"} tickFormatter={(value) => `${value}`} />
        <YAxis allowDecimals={false} />
        <Tooltip content={mode === "hot" ? <TrendTooltip scoreRows={scoreRows} /> : undefined} />
        {mode === "hot" && <Bar dataKey="missing" fill="#ef4d3c" radius={[3, 3, 0, 0]} />}
        <Bar dataKey={mode === "missing" ? "missing" : "count"} fill={mode === "ratio" ? "#31d86b" : mode === "missing" ? "#ef4d3c" : "#1768d7"} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLineChart({ data, compact = false, showDots = false }) {
  return (
    <ResponsiveContainer width="100%" height={compact ? 170 : 300}>
      <LineChart data={data}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="issue" hide />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="value" stroke="#53a3ff" strokeWidth={2} dot={showDots} />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function CapitalSpendChart({ data }) {
  return (
    <ResponsiveContainer width="100%" height={190}>
      <LineChart data={data}>
        <CartesianGrid stroke={gridStroke} vertical={false} />
        <XAxis dataKey="issue" />
        <YAxis />
        <Tooltip formatter={(value, name, item) => [`${value} 元（本期 ${item.payload.cost} 元）`, "累计投入"]} />
        <Line type="monotone" dataKey="value" stroke="#4ca6ff" strokeWidth={2} />
      </LineChart>
    </ResponsiveContainer>
  );
}
