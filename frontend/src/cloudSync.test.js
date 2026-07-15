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
