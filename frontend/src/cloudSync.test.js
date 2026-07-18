import assert from "node:assert/strict";
import test from "node:test";
import { mergeRecords, mergeSyncState } from "./cloudSync.js";

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
