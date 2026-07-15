import assert from "node:assert/strict";
import test from "node:test";

import { rotateItems, selectScoredCombination, topScoreNumbers } from "./suggestionRotation.js";

test("连续生成序号会轮换不同评分候选号码", () => {
  const rows = Array.from({ length: 10 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  const first = topScoreNumbers(rows, 10, 1).slice(0, 5);
  const second = topScoreNumbers(rows, 10, 2).slice(0, 5);

  assert.notDeepEqual(first, second);
  assert.ok(first.every((number) => number <= 8));
  assert.ok(second.every((number) => number <= 8));
});

test("轮换到号码池尾部后会安全回绕", () => {
  assert.deepEqual(rotateItems([1, 2, 3], 4), [2, 3, 1]);
});

test("后区候选按评分带变体选择，不按数字自然顺序", () => {
  const rows = [
    { number: 11, total_score: 96 },
    { number: 4, total_score: 91 },
    { number: 9, total_score: 87 },
    { number: 2, total_score: 82 },
    { number: 7, total_score: 79 },
    { number: 1, total_score: 75 },
    { number: 12, total_score: 72 },
    { number: 5, total_score: 68 },
  ];

  const selected = selectScoredCombination(rows, 12, 2, 1);
  assert.notDeepEqual(selected, [1, 2]);
  assert.ok(selected.every((number) => [11, 4, 9, 2, 7, 1, 12, 5].includes(number)));
});

test("后区组合在候选组合用完前不重复", () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ number: index + 1, total_score: 100 - index * 3 }));
  const signatures = Array.from({ length: 10 }, (_, index) => (
    selectScoredCombination(rows, 12, 2, index + 1).slice().sort((a, b) => a - b).join("-")
  ));
  assert.equal(new Set(signatures).size, signatures.length);
});
