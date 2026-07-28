import assert from "node:assert/strict";
import test from "node:test";
import { mergeRecords, mergeSyncState, normalizeBackupPayload } from "./cloudSync.js";

test("云同步合并记录并按 id 去重", () => {
  const older = { id: "same", saved_at: "2026-07-01T00:00:00Z", plan: { cost: 10 } };
  const newer = { id: "same", saved_at: "2026-07-02T00:00:00Z", plan: { cost: 20 } };
  const merged = mergeRecords([older], [newer]);
  assert.equal(merged.length, 1);
  assert.equal(merged[0].plan.cost, 20);
});

test("云同步同时保留大乐透与双色球记录", () => {
  const merged = mergeSyncState(
    { dlt_records: [{ id: "dlt" }], ssq_records: [] },
    { dlt_records: [], ssq_records: [{ id: "ssq" }] },
  );
  assert.equal(merged.dlt_records.length, 1);
  assert.equal(merged.ssq_records.length, 1);
});

test("云同步完整保留套餐结构、复式号码池和单式倍率", () => {
  const packageRecord = {
    id: "package",
    saved_at: "2026-07-18T00:00:00Z",
    plan: {
      mode: "package",
      multiplier: 3,
      package_entries: [
        { mode: "compound", front_pool: [1, 2, 3, 4, 5, 6], back_pool: [1, 2, 3] },
      ],
      items: [{ front: [1, 2, 3, 4, 5], back: [1, 2] }],
    },
  };
  const merged = mergeSyncState({ dlt_records: [packageRecord] }, {});
  assert.deepEqual(merged.dlt_records[0].plan, packageRecord.plan);
});

test("离线备份同时校验并保留两种彩票记录", () => {
  const normalized = normalizeBackupPayload(JSON.stringify({
    version: 1,
    dlt_records: [{ id: "dlt-backup" }],
    ssq_records: [{ id: "ssq-backup" }],
    updated_at: "2026-07-28T00:00:00Z",
  }));
  assert.equal(normalized.dlt_records[0].id, "dlt-backup");
  assert.equal(normalized.ssq_records[0].id, "ssq-backup");
});

test("离线备份缺少彩种记录时明确拒绝", () => {
  assert.throws(
    () => normalizeBackupPayload('{"dlt_records":[]}'),
    /缺少大乐透或双色球方案记录/,
  );
});

test("云同步最多保留每种彩票一千条记录", () => {
  const records = Array.from({ length: 1100 }, (_, index) => ({
    id: `record-${index}`,
    saved_at: new Date(2026, 0, index + 1).toISOString(),
  }));
  assert.equal(mergeRecords(records).length, 1000);
});

test("离线备份不会截断超过一千条的本地归档", () => {
  const records = Array.from({ length: 1100 }, (_, index) => ({
    id: `backup-${index}`,
    saved_at: new Date(2026, 0, index + 1).toISOString(),
  }));
  const normalized = normalizeBackupPayload({
    dlt_records: records,
    ssq_records: [],
  });
  assert.equal(normalized.dlt_records.length, 1100);
});
