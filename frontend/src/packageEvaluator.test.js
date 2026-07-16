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

test("每个套餐的结构元数据都能展开为标注的基础注数", () => {
  for (const scene of ["DLT", "SSQ"]) {
    const frontPick = scene === "DLT" ? 5 : 6;
    const backPick = scene === "DLT" ? 2 : 1;
    const combinations = (total, pick) => {
      let value = 1;
      for (let index = 1; index <= pick; index += 1) value = (value * (total - index + 1)) / index;
      return Math.round(value);
    };
    packageCatalog(scene).forEach((item) => {
      const tickets = item.components.reduce((sum, component) => (
        sum + (component.mode === "single" ? component.count : combinations(component.front, frontPick) * combinations(component.back, backPick))
      ), 0);
      assert.equal(tickets, item.baseTickets, `${scene} ${item.amount}元套餐结构不一致`);
    });
  }
});
