import assert from "node:assert/strict";
import test from "node:test";

import { hasConsecutiveNumbers, rotateItems, selectScoredCombination, topScoreNumbers } from "./suggestionRotation.js";

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

test("大乐透后区避开前区号码并优先排除连号", () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  const selected = selectScoredCombination(rows, 12, 2, 1, [1, 2], { avoidConsecutive: true });
  assert.equal(selected.some((number) => [1, 2].includes(number)), false);
  assert.equal(hasConsecutiveNumbers(selected), false);
});

test("大乐透多次生成的后区均不使用连号", () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ number: index + 1, total_score: 100 - index * 2 }));
  for (let variant = 1; variant <= 12; variant += 1) {
    const selected = selectScoredCombination(rows, 12, 2, variant, [1, 4], { avoidConsecutive: true });
    assert.equal(hasConsecutiveNumbers(selected), false);
  }
});

test("排除号码过多时会放宽分区去重但保持所选数量合法", () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  const selected = selectScoredCombination(rows, 12, 12, 1, [1, 2, 3, 4, 5, 6], { avoidConsecutive: true });
  assert.equal(selected.length, 12);
});

test("2胆和3胆都会随生成序号切换不同高分组合", () => {
  const rows = Array.from({ length: 35 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  for (const danCount of [2, 3]) {
    const signatures = Array.from({ length: 8 }, (_, index) => (
      selectScoredCombination(rows, 35, danCount, index + 1).slice().sort((a, b) => a - b).join("-")
    ));
    assert.equal(new Set(signatures).size, signatures.length);
  }
});

test("拖码组合会排除已选胆码", () => {
  const rows = Array.from({ length: 12 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  const dan = selectScoredCombination(rows, 12, 2, 2);
  const tuo = selectScoredCombination(rows, 12, 5, 2, dan);
  assert.equal(tuo.some((number) => dan.includes(number)), false);
});

test("双色球1至5胆会独立轮换且红球拖码不重复", () => {
  const rows = Array.from({ length: 33 }, (_, index) => ({ number: index + 1, total_score: 100 - index }));
  for (let danCount = 1; danCount <= 5; danCount += 1) {
    const signatures = Array.from({ length: 5 }, (_, index) => {
      const variant = index + 1;
      const dan = selectScoredCombination(rows, 33, danCount, variant);
      const tuo = selectScoredCombination(rows, 33, Math.max(6 - danCount, 5), variant, dan);
      assert.equal(tuo.some((number) => dan.includes(number)), false);
      return dan.slice().sort((a, b) => a - b).join("-");
    });
    assert.equal(new Set(signatures).size, signatures.length);
  }
});
