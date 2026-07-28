import assert from "node:assert/strict";
import test from "node:test";
import { mergeArchiveRecords, RECORD_SYNC_LIMIT } from "./recordStore.js";

test("方案归档不截断超过一百条的历史记录", () => {
  const records = Array.from({ length: 180 }, (_, index) => ({
    id: `record-${index}`,
    saved_at: new Date(2026, 0, index + 1).toISOString(),
  }));
  assert.equal(mergeArchiveRecords(records).length, 180);
});

test("云同步容量提高到每种彩票一千条", () => {
  assert.equal(RECORD_SYNC_LIMIT, 1000);
});
