import {
  getDemoDashboard,
  getDemoPlan,
  getDemoRecords,
  getDemoReview,
  getDemoBacktest,
  getDemoScenes,
  getDemoDraws,
  saveDemoRecord,
} from "./demoData";

const RAW_API_BASE = import.meta.env.VITE_API_BASE || "/api";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true"
  || window.location.hostname.endsWith("github.io");

function getApiBase() {
  if (/^https?:\/\//i.test(RAW_API_BASE)) {
    return RAW_API_BASE.replace(/\/$/, "");
  }
  const basePath = RAW_API_BASE.startsWith("/") ? RAW_API_BASE : `/${RAW_API_BASE}`;
  return `${window.location.origin}${basePath.replace(/\/$/, "")}`;
}

function buildApiUrl(path) {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBase()}${cleanPath}`;
}

function toQueryString(values) {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (value === "" || value === null || value === undefined) return;
    params.set(key, String(value));
  });
  return params.toString();
}

async function request(path, options = {}) {
  const hasBody = options.body !== undefined && !(options.body instanceof FormData);
  const response = await fetch(buildApiUrl(path), {
    headers: hasBody
      ? {
          "Content-Type": "application/json",
          ...(options.headers || {}),
        }
      : options.headers,
    ...options,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `API ${response.status}: ${response.statusText} (${path})`);
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
  const params = toQueryString({
    budget,
    last_prize: lastPrize,
    strategy,
    window,
    principal,
    level_units: levelUnits,
    balance,
  });
  return request(`/dashboard/dlt?${params}`);
}

export function generateDltPlan({ budget, strategy, lastPrize, window, principal, balance, levelUnits, variant = 0 }) {
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
      variant,
    }),
  });
}

export function getDltRecords() {
  if (STATIC_DEMO) return getDemoRecords();
  return request("/records/dlt");
}

export function deleteDltRecord(id) {
  if (STATIC_DEMO) {
    const records = JSON.parse(localStorage.getItem("ceway_demo_records") || "[]")
      .filter((record) => record.id !== id);
    localStorage.setItem("ceway_demo_records", JSON.stringify(records));
    return Promise.resolve({ status: "ok", deleted: true, id });
  }
  return request(`/records/dlt/${encodeURIComponent(id)}`, { method: "DELETE" });
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

export function getDltBacktest({ budget = 20, strategy = "balanced", periods = 100, window = 100 } = {}) {
  if (STATIC_DEMO) return getDemoBacktest({ budget, strategy, periods, window });
  const params = toQueryString({ budget, strategy, periods, window });
  return request(`/backtest/dlt?${params}`);
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
    return getDemoDraws(limit).then((items) => ({ items, total: items.length, limit, offset: 0, issue: "" }));
  }
  return request(`/data/dlt/draws?${toQueryString({ limit })}`);
}

export function searchDltDraws({ limit = 12, offset = 0, issue = "" } = {}) {
  if (STATIC_DEMO) {
    return getDemoDraws(30).then((items) => {
      const filtered = issue ? items.filter((item) => item.issue.includes(issue)) : items;
      return { items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset, issue };
    });
  }
  const params = toQueryString({ limit, offset, issue });
  return request(`/data/dlt/draws?${params}`);
}

export function syncDltHistory({ source = "sporttery", full = false } = {}) {
  if (STATIC_DEMO) {
    throw new Error("GitHub Pages 演示模式不支持联网更新，请在本地后端环境使用。");
  }
  const params = toQueryString({ source, full });
  return request(`/data/dlt/sync?${params}`, { method: "POST" });
}

export function getSsqDashboard({
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
  const params = toQueryString({
    budget,
    last_prize: lastPrize,
    strategy,
    window,
    principal,
    level_units: levelUnits,
    balance,
  });
  return request(`/dashboard/ssq?${params}`);
}

export function generateSsqPlan({ budget, strategy, lastPrize, window, principal, balance, levelUnits, variant = 0 }) {
  if (STATIC_DEMO) {
    return getDemoPlan({ budget, strategy, lastPrize, window, principal, balance, levelUnits });
  }
  return request("/plan/ssq", {
    method: "POST",
    body: JSON.stringify({
      budget,
      strategy,
      last_prize: lastPrize,
      window,
      principal,
      balance: balance === "" ? null : balance,
      level_units: levelUnits,
      variant,
    }),
  });
}

export function getSsqRecords() {
  if (STATIC_DEMO) return getDemoRecords();
  return request("/records/ssq");
}

export function deleteSsqRecord(id) {
  if (STATIC_DEMO) {
    const records = JSON.parse(localStorage.getItem("ceway_demo_records") || "[]")
      .filter((record) => record.id !== id);
    localStorage.setItem("ceway_demo_records", JSON.stringify(records));
    return Promise.resolve({ status: "ok", deleted: true, id });
  }
  return request(`/records/ssq/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export function saveSsqRecord({ budget, strategy, latestIssue, plan }) {
  if (STATIC_DEMO) return saveDemoRecord({ budget, strategy, latestIssue, plan });
  return request("/records/ssq", {
    method: "POST",
    body: JSON.stringify({
      budget,
      strategy,
      latest_issue: latestIssue,
      plan,
    }),
  });
}

export function getSsqReview() {
  if (STATIC_DEMO) return getDemoReview();
  return request("/review/ssq");
}

export function getSsqBacktest({ budget = 20, strategy = "balanced", periods = 100, window = 100 } = {}) {
  if (STATIC_DEMO) return getDemoBacktest({ budget, strategy, periods, window });
  const params = toQueryString({ budget, strategy, periods, window });
  return request(`/backtest/ssq?${params}`);
}

export function getSsqDataStatus() {
  if (STATIC_DEMO) {
    return Promise.resolve({
      storage: "static_demo",
      path: "GitHub Pages demo",
      draw_count: 100,
      record_count: 0,
      review_count: 0,
      first_issue: "2025001",
      first_date: "2025-01-02",
      latest_issue: "2025100",
      latest_date: "2025-08-21",
      quality: {
        level: "sample",
        label: "样例数据",
        message: "SSQ 演示环境使用样例数据。",
        missing_count: 0,
        missing_issues: [],
        year_ranges: [{ year: "2025", first: "2025001", last: "2025100", count: 100, missing_count: 0 }],
      },
      last_sync: null,
    });
  }
  return request("/data/ssq/status");
}

export function getSsqDraws({ limit = 10 } = {}) {
  if (STATIC_DEMO) {
    return getDemoDraws(limit).then((items) => ({ items, total: items.length, limit, offset: 0, issue: "" }));
  }
  return request(`/data/ssq/draws?${toQueryString({ limit })}`);
}

export function searchSsqDraws({ limit = 12, offset = 0, issue = "" } = {}) {
  if (STATIC_DEMO) {
    return getDemoDraws(30).then((items) => {
      const filtered = issue ? items.filter((item) => item.issue.includes(issue)) : items;
      return { items: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset, issue };
    });
  }
  const params = toQueryString({ limit, offset, issue });
  return request(`/data/ssq/draws?${params}`);
}

export function syncSsqHistory({ source = "78500", full = false } = {}) {
  if (STATIC_DEMO) {
    throw new Error("GitHub Pages 演示模式不支持联网更新，请在本地后端环境使用。");
  }
  const params = toQueryString({ source, full });
  return request(`/data/ssq/sync?${params}`, { method: "POST" });
}

export async function importSsqHistory(file) {
  if (STATIC_DEMO) {
    throw new Error("GitHub Pages 演示模式不支持导入 CSV，请在本地后端环境使用该功能。");
  }
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(buildApiUrl("/data/ssq/import"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `API ${response.status}: ${response.statusText}`);
  }

  return response.json();
}

export async function importDltHistory(file) {
  if (STATIC_DEMO) {
    throw new Error("GitHub Pages 演示模式不支持导入 CSV，请在本地后端环境使用该功能。");
  }
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(buildApiUrl("/data/dlt/import"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail || `API ${response.status}: ${response.statusText}`);
  }

  return response.json();
}
