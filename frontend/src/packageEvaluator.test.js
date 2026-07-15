import assert from "node:assert/strict";
import test from "node:test";

import { evaluatePackage, packageCatalog } from "./packageEvaluator.js";

test("双色球18元套餐只在确认活动后计入4元赠票", () => {
  const item = packageCatalog("SSQ")[0];
  const unconfirmed = evaluatePackage(item, { budget: 20, giftConfirmed: false });
  const confirmed = evaluatePackage(item, { budget: 20, giftConfirmed: true });

  assert.equal(unconfirmed.totalTickets, 9);
  assert.equal(unconfirmed.faceAmount, 18);
  assert.equal(confirmed.giftAmount, 4);
  assert.equal(confirmed.totalTickets, 11);
  assert.equal(confirmed.faceAmount, 22);
  assert.equal(confirmed.unitPaidCost, 1.64);
});

test("投注倍数同比扩大实付和赠票，不改变单注实付成本", () => {
  const item = packageCatalog("SSQ")[1];
  const single = evaluatePackage(item, { budget: 100, giftConfirmed: true, multiplier: 1 });
  const doubled = evaluatePackage(item, { budget: 100, giftConfirmed: true, multiplier: 2 });

  assert.equal(doubled.paid, single.paid * 2);
  assert.equal(doubled.giftTickets, single.giftTickets * 2);
  assert.equal(doubled.unitPaidCost, single.unitPaidCost);
});

test("大乐透88元套餐按组合结构展开为44注", () => {
  const item = packageCatalog("DLT")[3];
  const result = evaluatePackage(item, { budget: 88, giftConfirmed: false });

  assert.equal(result.totalTickets, 44);
  assert.equal(result.faceAmount, 88);
  assert.equal(result.unitPaidCost, 2);
  assert.equal(result.withinBudget, true);
});

