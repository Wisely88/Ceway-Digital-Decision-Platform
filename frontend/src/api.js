const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

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

export function getDltDashboard({ budget, lastPrize }) {
  return request(`/dashboard/dlt?budget=${budget}&last_prize=${lastPrize}`);
}

export function generateDltPlan({ budget, mode, lastPrize }) {
  return request("/plan/dlt", {
    method: "POST",
    body: JSON.stringify({
      budget,
      mode,
      last_prize: lastPrize,
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
