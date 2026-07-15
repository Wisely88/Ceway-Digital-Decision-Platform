import assert from "node:assert/strict";
import test from "node:test";

import { rotateItems, topScoreNumbers } from "./suggestionRotation.js";

test("连续生成序号会轮换不同评分候选号码", () => {
  const rows = Array.from({ length: 10 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  const first = topScoreNumbers(rows, 10, 1).slice(0, 5);
  const second = topScoreNumbers(rows, 10, 2).slice(0, 5);

  assert.notDeepEqual(first, second);
  assert.deepEqual(first, [2, 3, 4, 5, 6]);
  assert.deepEqual(second, [3, 4, 5, 6, 7]);
});

test("轮换到号码池尾部后会安全回绕", () => {
  assert.deepEqual(rotateItems([1, 2, 3], 4), [2, 3, 1]);
});

