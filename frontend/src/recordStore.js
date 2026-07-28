const DB_NAME = "ceway-record-archive";
const DB_VERSION = 1;
const STORE_NAME = "records";
const CLOUD_LIMIT = 1000;

const LEGACY_KEYS = {
  DLT: ["ceway_demo_records", "cbgo_saved_plans"],
  SSQ: ["ceway_demo_ssq_records", "cbgo_ssq_plans"],
};

function sceneCode(scene) {
  return String(scene || "").toUpperCase() === "SSQ" ? "SSQ" : "DLT";
}

function identity(record) {
  if (record?.id) return String(record.id);
  const plan = record?.plan || record || {};
  return JSON.stringify([record?.saved_at, record?.latest_issue, plan.mode, plan.cost, plan.front_dan, plan.front_tuo, plan.back, plan.items]);
}

export function mergeArchiveRecords(...groups) {
  const records = new Map();
  groups.flat().forEach((record) => {
    if (!record || typeof record !== "object") return;
    const key = identity(record);
    const existing = records.get(key);
    if (!existing || String(record.saved_at || "") >= String(existing.saved_at || "")) records.set(key, record);
  });
  return [...records.values()].sort((left, right) => String(right.saved_at || "").localeCompare(String(left.saved_at || "")));
}

function readLegacy(scene) {
  if (typeof localStorage === "undefined") return [];
  return mergeArchiveRecords(...LEGACY_KEYS[sceneCode(scene)].map((key) => {
    try {
      const parsed = JSON.parse(localStorage.getItem(key) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }));
}

function writeCompatibilityCache(scene, records) {
  if (typeof localStorage === "undefined") return;
  const key = sceneCode(scene) === "SSQ" ? "ceway_demo_ssq_records" : "ceway_demo_records";
  try {
    localStorage.setItem(key, JSON.stringify(records.slice(0, CLOUD_LIMIT)));
    LEGACY_KEYS[sceneCode(scene)].filter((legacyKey) => legacyKey !== key).forEach((legacyKey) => localStorage.removeItem(legacyKey));
  } catch {
    // IndexedDB remains canonical when the compatibility cache reaches browser quota.
  }
}

function openDatabase() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("当前浏览器不支持 IndexedDB"));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const database = request.result;
      const store = database.createObjectStore(STORE_NAME, { keyPath: "_archive_key" });
      store.createIndex("scene", "_scene", { unique: false });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("无法打开方案归档"));
  });
}

function completeTransaction(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error || new Error("方案归档写入失败"));
    transaction.onabort = () => reject(transaction.error || new Error("方案归档写入已中止"));
  });
}

function storedRecord(scene, record) {
  const code = sceneCode(scene);
  return { ...record, _scene: code, _archive_key: `${code}:${identity(record)}` };
}

function publicRecord(record) {
  const { _scene, _archive_key, ...value } = record;
  return value;
}

async function migrateLegacyRecords(scene, database) {
  const code = sceneCode(scene);
  const marker = `ceway_archive_migrated_${code.toLowerCase()}`;
  if (localStorage.getItem(marker) === "true") return;
  const legacy = readLegacy(code);
  if (legacy.length) {
    const transaction = database.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    legacy.forEach((record) => store.put(storedRecord(code, record)));
    await completeTransaction(transaction);
  }
  localStorage.setItem(marker, "true");
}

export async function listArchivedRecords(scene) {
  const code = sceneCode(scene);
  try {
    const database = await openDatabase();
    await migrateLegacyRecords(code, database);
    const records = await new Promise((resolve, reject) => {
      const request = database.transaction(STORE_NAME).objectStore(STORE_NAME).index("scene").getAll(code);
      request.onsuccess = () => resolve(request.result.map(publicRecord));
      request.onerror = () => reject(request.error || new Error("无法读取方案归档"));
    });
    database.close();
    const sorted = mergeArchiveRecords(records);
    writeCompatibilityCache(code, sorted);
    return sorted;
  } catch {
    return readLegacy(code);
  }
}

export async function archiveRecord(scene, record) {
  const code = sceneCode(scene);
  try {
    const database = await openDatabase();
    await migrateLegacyRecords(code, database);
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).put(storedRecord(code, record));
    await completeTransaction(transaction);
    database.close();
    const records = await listArchivedRecords(code);
    return { record, count: records.length };
  } catch {
    const records = mergeArchiveRecords([record], readLegacy(code));
    writeCompatibilityCache(code, records);
    return { record, count: records.length };
  }
}

export async function archiveRecords(scene, records) {
  const code = sceneCode(scene);
  try {
    const database = await openDatabase();
    await migrateLegacyRecords(code, database);
    const transaction = database.transaction(STORE_NAME, "readwrite");
    const store = transaction.objectStore(STORE_NAME);
    records.forEach((record) => store.put(storedRecord(code, record)));
    await completeTransaction(transaction);
    database.close();
    return listArchivedRecords(code);
  } catch {
    const merged = mergeArchiveRecords(records, readLegacy(code));
    writeCompatibilityCache(code, merged);
    return merged;
  }
}

export async function deleteArchivedRecord(scene, id) {
  const code = sceneCode(scene);
  const records = await listArchivedRecords(code);
  const target = records.find((record) => record.id === id);
  if (!target) return false;
  try {
    const database = await openDatabase();
    const transaction = database.transaction(STORE_NAME, "readwrite");
    transaction.objectStore(STORE_NAME).delete(`${code}:${identity(target)}`);
    await completeTransaction(transaction);
    database.close();
  } catch {
    // Compatibility cache deletion still works when IndexedDB is unavailable.
  }
  writeCompatibilityCache(code, records.filter((record) => record.id !== id));
  return true;
}

export const RECORD_SYNC_LIMIT = CLOUD_LIMIT;
