import assert from "node:assert/strict";
import test from "node:test";

import { paginateDraws } from "./drawPagination.js";

const history = Array.from({ length: 30 }, (_, index) => ({ issue: String(index + 1).padStart(5, "0") }));

test("开奖记录返回完整总期数而不是当前页条数", () => {
  const page = paginateDraws(history, { limit: 12, offset: 0, issue: "" });
  assert.equal(page.items.length, 12);
  assert.ok(page.total > page.items.length);
});

test("开奖记录可翻页并保持总期数", () => {
  const first = paginateDraws(history, { limit: 12, offset: 0, issue: "" });
  const second = paginateDraws(history, { limit: 12, offset: 12, issue: "" });
  assert.equal(first.items.length, 12);
  assert.equal(second.items.length, 12);
  assert.ok(first.total > 24);
  assert.notEqual(first.items[0].issue, second.items[0].issue);
});
