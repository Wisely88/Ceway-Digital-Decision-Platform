import { createClient } from "@supabase/supabase-js";

const SUPABASE_URL = "https://pxnhzlcdmskmfaoqzaco.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_UfK279eijJnDtJfwP0TWSg_snoIFfsJ";
const SYNC_EMAIL = "ceway-sync@ceway.local";
const AUTO_SYNC_KEY = "ceway_cloud_auto_sync";
const RECORD_KEYS = {
  dlt: ["ceway_demo_records", "cbgo_saved_plans"],
  ssq: ["ceway_demo_ssq_records", "cbgo_ssq_plans"],
};

export const cloudClient = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});

function readRecords(keys) {
  return keys.flatMap((key) => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(value) ? value : [];
    } catch {
      return [];
    }
  });
}

function recordIdentity(record) {
  if (record?.id) return String(record.id);
  const plan = record?.plan || record || {};
  return JSON.stringify([record?.saved_at, record?.latest_issue, plan.mode, plan.cost, plan.front_dan, plan.front_tuo, plan.back, plan.items]);
}

export function mergeRecords(...groups) {
  const records = new Map();
  groups.flat().forEach((record) => {
    if (!record || typeof record !== "object") return;
    const key = recordIdentity(record);
    const existing = records.get(key);
    if (!existing || String(record.saved_at || "") >= String(existing.saved_at || "")) records.set(key, record);
  });
  return [...records.values()]
    .sort((left, right) => String(right.saved_at || "").localeCompare(String(left.saved_at || "")))
    .slice(0, 100);
}

export function collectLocalState() {
  return {
    version: 1,
    dlt_records: mergeRecords(readRecords(RECORD_KEYS.dlt)),
    ssq_records: mergeRecords(readRecords(RECORD_KEYS.ssq)),
    updated_at: new Date().toISOString(),
  };
}

export function mergeSyncState(local = {}, remote = {}) {
  return {
    version: 1,
    dlt_records: mergeRecords(local.dlt_records || [], remote.dlt_records || []),
    ssq_records: mergeRecords(local.ssq_records || [], remote.ssq_records || []),
    updated_at: new Date().toISOString(),
  };
}

export function applyLocalState(state) {
  localStorage.setItem("ceway_demo_records", JSON.stringify(state.dlt_records || []));
  localStorage.setItem("ceway_demo_ssq_records", JSON.stringify(state.ssq_records || []));
}

export function mirrorCloudRecord(scene, record) {
  const key = scene === "SSQ" ? "ceway_demo_ssq_records" : "ceway_demo_records";
  const records = readRecords([key]);
  localStorage.setItem(key, JSON.stringify(mergeRecords([record], records)));
}

export function removeCloudRecord(scene, id) {
  const key = scene === "SSQ" ? "ceway_demo_ssq_records" : "ceway_demo_records";
  const records = readRecords([key]).filter((record) => record.id !== id);
  localStorage.setItem(key, JSON.stringify(records));
}

export function isAutoSyncEnabled() {
  return localStorage.getItem(AUTO_SYNC_KEY) !== "false";
}

export function setAutoSyncEnabled(enabled) {
  localStorage.setItem(AUTO_SYNC_KEY, enabled ? "true" : "false");
}

export async function getCloudSession() {
  const { data, error } = await cloudClient.auth.getSession();
  if (error) throw error;
  return data.session;
}

export async function signInCloud(password) {
  const { data, error } = await cloudClient.auth.signInWithPassword({ email: SYNC_EMAIL, password });
  if (error) throw error;
  return data.session;
}

export async function signOutCloud() {
  const { error } = await cloudClient.auth.signOut({ scope: "local" });
  if (error) throw error;
}

export async function syncCloudState() {
  const session = await getCloudSession();
  if (!session?.user) throw new Error("请先输入同步密码");
  const { data: remoteRow, error: readError } = await cloudClient
    .from("ceway_sync_state")
    .select("payload,updated_at")
    .eq("user_id", session.user.id)
    .maybeSingle();
  if (readError) throw readError;
  const merged = mergeSyncState(collectLocalState(), remoteRow?.payload || {});
  const { error: writeError } = await cloudClient.from("ceway_sync_state").upsert({
    user_id: session.user.id,
    payload: merged,
    updated_at: new Date().toISOString(),
  });
  if (writeError) throw writeError;
  applyLocalState(merged);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("ceway-cloud-state-applied"));
  }
  return {
    state: merged,
    dlt_count: merged.dlt_records.length,
    ssq_count: merged.ssq_records.length,
    updated_at: merged.updated_at,
  };
}

export function notifyCloudDataChanged() {
  window.dispatchEvent(new CustomEvent("ceway-cloud-data-changed"));
}
