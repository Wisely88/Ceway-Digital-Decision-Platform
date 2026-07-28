import React, { useEffect, useRef, useState } from "react";
import { Cloud, CloudOff, Download, LogOut, RefreshCw, ShieldCheck, Upload } from "lucide-react";
import {
  cloudClient,
  collectLocalState,
  getCloudSession,
  importLocalBackup,
  isAutoSyncEnabled,
  setAutoSyncEnabled,
  signInCloud,
  signOutCloud,
  syncCloudState,
} from "./cloudSync";

function readableError(error) {
  const message = String(error?.message || error || "云同步失败");
  if (message.includes("Invalid login credentials")) return "同步密码不正确，或云端内部账号尚未创建。";
  if (message.includes("ceway_sync_state") || message.includes("schema cache")) return "云端数据表尚未初始化，请先执行项目中的 Supabase 初始化脚本。";
  return message;
}

export function CloudSyncAgent() {
  useEffect(() => {
    let timer;
    const sync = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(async () => {
        if (!isAutoSyncEnabled()) return;
        try {
          if (await getCloudSession()) await syncCloudState();
        } catch {
          // Manual sync remains available for recovery and detailed feedback.
        }
      }, 600);
    };
    window.addEventListener("ceway-cloud-data-changed", sync);
    sync();
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener("ceway-cloud-data-changed", sync);
    };
  }, []);
  return null;
}

export default function CloudSyncPanel({ scene = "DLT", onApply }) {
  const fileInputRef = useRef(null);
  const [session, setSession] = useState(null);
  const [password, setPassword] = useState("");
  const [autoSync, setAutoSync] = useState(isAutoSyncEnabled());
  const [status, setStatus] = useState("正在检查云端状态...");
  const [busy, setBusy] = useState(false);
  const [lastSync, setLastSync] = useState(null);

  useEffect(() => {
    getCloudSession().then((current) => {
      setSession(current);
      setStatus(current ? "云同步已连接" : "尚未连接云同步");
    }).catch((error) => setStatus(readableError(error)));
    const { data } = cloudClient.auth.onAuthStateChange((_event, current) => setSession(current));
    return () => data.subscription.unsubscribe();
  }, []);

  const syncNow = async () => {
    setBusy(true);
    try {
      const result = await syncCloudState();
      const records = scene === "SSQ" ? result.state.ssq_records : result.state.dlt_records;
      if (onApply) await onApply(records);
      setLastSync(result);
      setStatus(`同步完成：大乐透 ${result.dlt_count} 条，双色球 ${result.ssq_count} 条。`);
    } catch (error) {
      setStatus(readableError(error));
    } finally {
      setBusy(false);
    }
  };

  const connect = async () => {
    if (password.length < 8) {
      setStatus("同步密码至少需要 8 位。");
      return;
    }
    setBusy(true);
    try {
      const current = await signInCloud(password);
      setSession(current);
      setPassword("");
      await syncNow();
    } catch (error) {
      setStatus(readableError(error));
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await signOutCloud();
      setSession(null);
      setStatus("本设备已断开云同步，本地数据仍然保留。");
    } catch (error) {
      setStatus(readableError(error));
    } finally {
      setBusy(false);
    }
  };

  const exportBackup = () => {
    const state = collectLocalState();
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `ceway-backup-${new Date().toISOString().slice(0, 10)}.json`;
    anchor.click();
    URL.revokeObjectURL(url);
    setStatus(`本地备份已导出：大乐透 ${state.dlt_records.length} 条，双色球 ${state.ssq_records.length} 条。`);
  };

  const importBackup = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusy(true);
    try {
      const state = importLocalBackup(await file.text());
      const records = scene === "SSQ" ? state.ssq_records : state.dlt_records;
      if (onApply) await onApply(records);
      setStatus(`本地备份已恢复：大乐透 ${state.dlt_records.length} 条，双色球 ${state.ssq_records.length} 条。`);
    } catch (error) {
      setStatus(`恢复失败：${readableError(error)}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel wide cloud-sync-panel" id="module-cloud">
      <div className="panel-title">
        <div>
          <h2>云端同步</h2>
          <p>自用单用户模式 · 不开放注册 · 本地数据始终保留</p>
        </div>
        <span className={`cloud-status ${session ? "connected" : ""}`}>
          {session ? <Cloud size={16} /> : <CloudOff size={16} />}{session ? "已连接" : "未连接"}
        </span>
      </div>

      {!session ? (
        <div className="cloud-connect">
          <div>
            <h3>输入同步密码</h3>
            <p>所有自用设备输入同一个密码。系统不会显示邮箱、注册或用户管理。</p>
          </div>
          <input autoComplete="current-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="至少 8 位同步密码" />
          <button className="primary-button" disabled={busy || !password} onClick={connect} type="button"><Cloud size={16} />开启云同步</button>
        </div>
      ) : (
        <div className="cloud-connected">
          <div className="cloud-security"><ShieldCheck size={22} /><div><strong>设备已安全连接</strong><span>每位云端用户只能读取自己的方案数据。</span></div></div>
          <label className="cloud-toggle"><input checked={autoSync} type="checkbox" onChange={(event) => { setAutoSync(event.target.checked); setAutoSyncEnabled(event.target.checked); }} />方案变化后自动同步</label>
          <div className="cloud-actions">
            <button className="primary-button" disabled={busy} onClick={syncNow} type="button"><RefreshCw className={busy ? "spin" : ""} size={16} />立即同步</button>
            <button className="ghost-button" disabled={busy} onClick={disconnect} type="button"><LogOut size={16} />断开本设备</button>
          </div>
        </div>
      )}
      <p className="cloud-message">{status}</p>
      {lastSync && <p className="cloud-last-sync">最后同步：{new Date(lastSync.updated_at).toLocaleString("zh-CN", { hour12: false })}</p>}

      <div className="cloud-connected local-backup">
        <div className="cloud-security">
          <ShieldCheck size={22} />
          <div><strong>本地离线备份</strong><span>无需登录，可将两种彩票的已选方案导出为文件，并在任意浏览器恢复。</span></div>
        </div>
        <div className="cloud-actions">
          <button className="ghost-button" disabled={busy} onClick={exportBackup} type="button"><Download size={16} />导出备份</button>
          <button className="ghost-button" disabled={busy} onClick={() => fileInputRef.current?.click()} type="button"><Upload size={16} />恢复备份</button>
          <input ref={fileInputRef} accept="application/json,.json" hidden onChange={importBackup} type="file" />
        </div>
      </div>
    </section>
  );
}
