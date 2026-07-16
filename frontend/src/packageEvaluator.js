const DLT_PACKAGES = [
  { amount: 18, structure: "单式6注 + 5+3复式", baseTickets: 9, components: [{ mode: "single", count: 6 }, { mode: "compound", front: 5, back: 3 }] },
  { amount: 28, structure: "单式8注 + 6+2复式", baseTickets: 14, components: [{ mode: "single", count: 8 }, { mode: "compound", front: 6, back: 2 }] },
  { amount: 58, structure: "单式8注 + 7+2复式", baseTickets: 29, components: [{ mode: "single", count: 8 }, { mode: "compound", front: 7, back: 2 }] },
  { amount: 88, structure: "单式5注 + 6+3复式 + 7+2复式", baseTickets: 44, components: [{ mode: "single", count: 5 }, { mode: "compound", front: 6, back: 3 }, { mode: "compound", front: 7, back: 2 }] },
];

const SSQ_PACKAGES = [
  { amount: 18, structure: "单式5注 + 6+4复式", baseTickets: 9, components: [{ mode: "single", count: 5 }, { mode: "compound", front: 6, back: 4 }], giftAmount: 4, giftTickets: 2, giftStructure: "6+2复式", giftComponent: { mode: "compound", front: 6, back: 2 }, blueDistinct: true },
  { amount: 28, structure: "7+1复式 + 6+7复式", baseTickets: 14, components: [{ mode: "compound", front: 7, back: 1 }, { mode: "compound", front: 6, back: 7 }], giftAmount: 6, giftTickets: 3, giftStructure: "6+3复式", giftComponent: { mode: "compound", front: 6, back: 3 }, blueDistinct: true },
  { amount: 38, structure: "单式5注 + 7+2复式", baseTickets: 19, components: [{ mode: "single", count: 5 }, { mode: "compound", front: 7, back: 2 }], giftAmount: 8, giftTickets: 4, giftStructure: "6+4复式", giftComponent: { mode: "compound", front: 6, back: 4 }, blueDistinct: true },
  { amount: 66, structure: "单式5注 + 8+1复式", baseTickets: 33, components: [{ mode: "single", count: 5 }, { mode: "compound", front: 8, back: 1 }], giftAmount: 14, giftTickets: 7, giftStructure: "6+7复式", giftComponent: { mode: "compound", front: 6, back: 7 }, blueDistinct: true },
  { amount: 88, structure: "6+16复式 + 8+1复式", baseTickets: 44, components: [{ mode: "compound", front: 6, back: 16 }, { mode: "compound", front: 8, back: 1 }], giftAmount: 20, giftTickets: 10, giftStructure: "6+10复式", giftComponent: { mode: "compound", front: 6, back: 10 }, blueDistinct: false },
];

export const PACKAGE_SOURCES = {
  DLT: {
    label: "大乐透标准套餐票",
    region: "部分地区有售，以当地终端为准",
    sourceUrl: "https://m.lottery.gov.cn/zx/zj/20260429/10053451.html",
    activity: "当前不计入额外赠票或已结束派奖权益。",
  },
  SSQ: {
    label: "江苏福彩双色球套餐赠票",
    region: "仅江苏省福彩销售网点",
    sourceUrl: "https://www.jslottery.com/articles/45623020-2cbc-46ef-89d4-77e77ca8f41e?locale=zh-CN",
    activity: "自第2026080期起，至500万元赠票资金用完为止。",
  },
};

export function packageCatalog(scene) {
  return scene === "SSQ" ? SSQ_PACKAGES : DLT_PACKAGES;
}

export function evaluatePackage(item, { multiplier = 1, giftConfirmed = false, budget = 0 } = {}) {
  const safeMultiplier = Math.max(1, Math.floor(Number(multiplier) || 1));
  const paid = item.amount * safeMultiplier;
  const baseTickets = item.baseTickets * safeMultiplier;
  const giftAmount = giftConfirmed ? (item.giftAmount || 0) * safeMultiplier : 0;
  const giftTickets = giftConfirmed ? (item.giftTickets || 0) * safeMultiplier : 0;
  const faceAmount = paid + giftAmount;
  const totalTickets = baseTickets + giftTickets;

  return {
    ...item,
    multiplier: safeMultiplier,
    paid,
    baseTickets,
    giftAmount,
    giftTickets,
    faceAmount,
    totalTickets,
    unitPaidCost: Number((paid / Math.max(1, totalTickets)).toFixed(2)),
    budgetUtilization: Number(((paid / Math.max(1, Number(budget) || paid)) * 100).toFixed(1)),
    withinBudget: paid <= Number(budget || 0),
    benefitStatus: giftAmount > 0 ? "已计入赠票" : "未计入赠票",
  };
}
