const PREFIX = "CEWAY1.";
const MAX_RECORDS = 100;
const MAX_CODE_LENGTH = 2_000_000;

function bytesToBase64(bytes) {
  let binary = "";
  bytes.forEach((byte) => { binary += String.fromCharCode(byte); });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64ToBytes(value) {
  const normalized = value.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const binary = atob(padded);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

export function encodeSyncBundle(scene, records) {
  const normalizedScene = String(scene || "").toUpperCase();
  if (!["DLT", "SSQ"].includes(normalizedScene)) throw new Error("仅支持大乐透和双色球同步");
  const payload = {
    version: 1,
    scene: normalizedScene,
    exported_at: new Date().toISOString(),
    records: (Array.isArray(records) ? records : []).slice(0, MAX_RECORDS),
  };
  return `${PREFIX}${bytesToBase64(new TextEncoder().encode(JSON.stringify(payload)))}`;
}

export function decodeSyncBundle(code, expectedScene) {
  const text = String(code || "").trim();
  if (!text.startsWith(PREFIX)) throw new Error("同步码格式不正确");
  if (text.length > MAX_CODE_LENGTH) throw new Error("同步码超过大小上限");
  let payload;
  try {
    payload = JSON.parse(new TextDecoder().decode(base64ToBytes(text.slice(PREFIX.length))));
  } catch {
    throw new Error("同步码已损坏或不完整");
  }
  if (payload?.version !== 1 || !Array.isArray(payload.records)) throw new Error("不支持该同步码版本");
  if (!["DLT", "SSQ"].includes(payload.scene)) throw new Error("同步码场景不正确");
  if (expectedScene && payload.scene !== String(expectedScene).toUpperCase()) throw new Error(`这是${payload.scene}同步码，请进入对应场景导入`);
  if (payload.records.length > MAX_RECORDS) throw new Error("同步记录数量超过上限");
  return payload;
}
