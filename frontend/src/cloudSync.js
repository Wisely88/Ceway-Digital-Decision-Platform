import { createClient } from "@supabase/supabase-js";
import {
  archiveRecord,
  archiveRecords,
  deleteArchivedRecord,
  listArchivedRecords,
  mergeArchiveRecords,
  RECORD_SYNC_LIMIT,
} from "./recordStore.js";

const SUPABASE_URL = "https://pxnhzlcdmskmfaoqzaco.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_UfK279eijJnDtJfwP0TWSg_snoIFfsJ";
const SYNC_EMAIL = "ceway-sync@ceway.local";
const AUTO_SYNC_KEY = "ceway_cloud_auto_sync";

export const cloudClient = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});

export function mergeRecords(...groups) {
  return mergeArchiveRecords(...groups).slice(0, RECORD_SYNC_LIMIT);
}

export async function collectLocalState({ limit = null } = {}) {
  const dltRecords = await listArchivedRecords("DLT");
  const ssqRecords = await listArchivedRecords("SSQ");
  return {
    version: 1,
    dlt_records: limit ? mergeArchiveRecords(dltRecords).slice(0, limit) : mergeArchiveRecords(dltRecords),
    ssq_records: limit ? mergeArchiveRecords(ssqRecords).slice(0, limit) : mergeArchiveRecords(ssqRecords),
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

export async function applyLocalState(state) {
  await Promise.all([
    archiveRecords("DLT", state.dlt_records || []),
    archiveRecords("SSQ", state.ssq_records || []),
  ]);
}

export function normalizeBackupPayload(payload) {
  const parsed = typeof payload === "string" ? JSON.parse(payload) : payload;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("备份文件格式无效");
  }
  if (!Array.isArray(parsed.dlt_records) || !Array.isArray(parsed.ssq_records)) {
    throw new Error("备份文件缺少大乐透或双色球方案记录");
  }
  return {
    version: 1,
    dlt_records: mergeArchiveRecords(parsed.dlt_records),
    ssq_records: mergeArchiveRecords(parsed.ssq_records),
    updated_at: parsed.updated_at || new Date().toISOString(),
  };
}

export async function importLocalBackup(payload) {
  const imported = normalizeBackupPayload(payload);
  const local = await collectLocalState();
  const merged = {
    version: 1,
    dlt_records: mergeArchiveRecords(local.dlt_records, imported.dlt_records),
    ssq_records: mergeArchiveRecords(local.ssq_records, imported.ssq_records),
    updated_at: new Date().toISOString(),
  };
  await applyLocalState(merged);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent("ceway-cloud-state-applied"));
  }
  return merged;
}

export async function mirrorCloudRecord(scene, record) {
  await archiveRecord(scene, record);
}

export async function removeCloudRecord(scene, id) {
  await deleteArchivedRecord(scene, id);
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
  const merged = mergeSyncState(
    await collectLocalState({ limit: RECORD_SYNC_LIMIT }),
    remoteRow?.payload || {},
  );
  const { error: writeError } = await cloudClient.from("ceway_sync_state").upsert({
    user_id: session.user.id,
    payload: merged,
    updated_at: new Date().toISOString(),
  });
  if (writeError) throw writeError;
  await applyLocalState(merged);
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
