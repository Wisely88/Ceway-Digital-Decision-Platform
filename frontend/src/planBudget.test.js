import assert from "node:assert/strict";
import test from "node:test";

import { fitCombinedPlanInputs } from "./planBudget.js";

test("大乐透三种玩法共享20元预算", () => {
  const result = fitCombinedPlanInputs({
    rules: { frontPick: 5, backPick: 2, frontMax: 35, backMax: 12 },
    budget: 20,
    unitPrice: 2,
    ticketCount: 5,
    singleMultiplier: 1,
    danCount: 2,
    tuoCount: 5,
    compoundFrontCount: 6,
    backCount: 2,
  });

  assert.equal(result.fits, true);
  assert.equal(result.cost, 20);
  assert.equal(result.tuoCount, 3);
  assert.equal(result.compoundFrontCount, 6);
  assert.equal(result.ticketCount, 3);
});

test("双色球三种玩法共享20元预算", () => {
  const result = fitCombinedPlanInputs({
    rules: { frontPick: 6, backPick: 1, frontMax: 33, backMax: 16 },
    budget: 20,
    unitPrice: 2,
    ticketCount: 5,
    singleMultiplier: 1,
    danCount: 3,
    tuoCount: 5,
    compoundFrontCount: 7,
    backCount: 1,
  });

  assert.equal(result.fits, true);
  assert.equal(result.cost, 20);
  assert.equal(result.ticketCount, 2);
});

test("追加投注预算不足时返回最低金额", () => {
  const result = fitCombinedPlanInputs({
    rules: { frontPick: 5, backPick: 2, frontMax: 35, backMax: 12 },
    budget: 20,
    unitPrice: 3,
    ticketCount: 5,
    singleMultiplier: 1,
    danCount: 2,
    tuoCount: 5,
    compoundFrontCount: 6,
    backCount: 2,
  });

  assert.equal(result.fits, false);
  assert.equal(result.minimumCost, 24);
});
