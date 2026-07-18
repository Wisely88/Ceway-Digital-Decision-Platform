import assert from "node:assert/strict";
import test from "node:test";

import { createRecordId } from "./recordIdentity.js";

test("同一毫秒批量保存也会生成不同记录 ID", () => {
  const ids = Array.from({ length: 6 }, () => createRecordId("demo", () => 1000, null));
  assert.equal(new Set(ids).size, ids.length);
});

test("浏览器支持 UUID 时优先使用 UUID", () => {
  assert.equal(createRecordId("ssq", Date.now, () => "fixed-uuid"), "ssq-fixed-uuid");
});
