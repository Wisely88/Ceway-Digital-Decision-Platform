import {
  getDemoDashboard,
  getDemoPlan,
  getDemoRecords,
  getDemoReview,
  getDemoScenes,
  getDemoDraws,
  saveDemoRecord,
} from "./demoData";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true"
  || window.location.hostname.endsWith("github.io");

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

export function getScenes() {
  if (STATIC_DEMO) return getDemoScenes();
  return request("/scenes");
}

export function getDltDashboard({
  budget,
  lastPrize,
  strategy,
  window,
  principal,
  balance,
  levelUnits,
}) {
  if (STATIC_DEMO) {
    return getDemoDashboard({ budget, lastPrize, strategy, window, principal, balance, levelUnits });
  }
  const params = new URLSearchParams({
    budget,
    last_prize: lastPrize,
    strategy,
    window,
    principal,
    level_units: levelUnits,
  });
  if (balance !== "" && balance !== null && balance !== undefined) {
    params.set("balance", balance);
  }
  return request(`/dashboard/dlt?${params.toString()}`);
}

export function generateDltPlan({ budget, strategy, lastPrize, window, principal, balance, levelUnits }) {
  if (STATIC_DEMO) {
    return getDemoPlan({ budget, strategy, lastPrize, window, principal, balance, levelUnits });
  }
  return request("/plan/dlt", {
    method: "POST",
    body: JSON.stringify({
      budget,
      strategy,
      last_prize: lastPrize,
      window,
      principal,
      balance: balance === "" ? null : balance,
      level_units: levelUnits,
    }),
  });
}

export function getDltRecords() {
  if (STATIC_DEMO) return getDemoRecords();
  return request("/records/dlt");
}

export function saveDltRecord({ budget, strategy, latestIssue, plan }) {
  if (STATIC_DEMO) return saveDemoRecord({ budget, strategy, latestIssue, plan });
  return request("/records/dlt", {
    method: "POST",
    body: JSON.stringify({
      budget,
      strategy,
      latest_issue: latestIssue,
      plan,
    }),
  });
}

export function getDltReview() {
  if (STATIC_DEMO) return getDemoReview();
  return request("/review/dlt");
}

export function getDltDataStatus() {
  if (STATIC_DEMO) {
    return Promise.resolve({
      storage: "static_demo",
      path: "GitHub Pages demo",
      draw_count: 30,
      record_count: JSON.parse(localStorage.getItem("ceway_demo_records") || "[]").length,
      review_count: 1,
      first_issue: "2025001",
      first_date: "2025-01-01",
      latest_issue: "2025030",
      latest_date: "2025-03-10",
      quality: {
        level: "sample",
        label: "样例数据",
        message: "GitHub Pages 演示环境使用内置样例数据，本地环境可通过 CSV 或脚本更新 SQLite。",
        missing_count: 0,
        missing_issues: [],
        year_ranges: [{ year: "2025", first: "2025001", last: "2025030", count: 30, missing_count: 0 }],
      },
      last_sync: null,
    });
  }
  return request("/data/dlt/status");
}

export function getDltDraws({ limit = 10 } = {}) {
  if (STATIC_DEMO) {
    return getDemoDraws(limit);
  }
  return request(`/data/dlt/draws?limit=${limit}`);
}

export async function importDltHistory(file) {
  if (STATIC_DEMO) {
    throw new Error("GitHub Pages 演示模式不支持导入 CSV，请在本地后端环境使用该功能。");
  }
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE}/data/dlt/import`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `API ${response.status}: ${response.statusText}`);
  }

  return response.json();
}
