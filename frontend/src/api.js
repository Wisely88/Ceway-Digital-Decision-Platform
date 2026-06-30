const API_BASE = import.meta.env.VITE_API_BASE || "/api";

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
  return request("/records/dlt");
}

export function saveDltRecord({ budget, strategy, latestIssue, plan }) {
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

export async function importDltHistory(file) {
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
