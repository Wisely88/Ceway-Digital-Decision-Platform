function combinationCount(n, k) {
  if (k < 0 || n < k) return 0;
  if (k === 0 || n === k) return 1;
  const safeK = Math.min(k, n - k);
  let result = 1;
  for (let index = 1; index <= safeK; index += 1) {
    result = (result * (n - safeK + index)) / index;
  }
  return Math.round(result);
}

function clampInteger(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, Math.floor(Number(value) || minimum)));
}

export function fitCombinedPlanInputs({
  rules,
  budget,
  unitPrice,
  ticketCount,
  singleMultiplier,
  danCount,
  tuoCount,
  compoundFrontCount,
  backCount,
}) {
  const safeBudget = Math.max(0, Number(budget) || 0);
  const safeUnitPrice = Math.max(1, Number(unitPrice) || 2);
  const safeDan = clampInteger(danCount, 1, rules.frontPick - 1);
  const minimumTuo = rules.frontPick - safeDan;
  const requestedTuo = clampInteger(tuoCount, minimumTuo, rules.frontMax - safeDan);
  const minimumCompoundFront = rules.frontPick + 1;
  const requestedCompoundFront = clampInteger(compoundFrontCount, minimumCompoundFront, rules.frontMax);
  const requestedBack = clampInteger(backCount, rules.backPick, rules.backMax);
  const requestedSingles = clampInteger(ticketCount, 1, 100);
  const safeMultiplier = clampInteger(singleMultiplier, 1, 99);
  const paidTicketCap = Math.floor(safeBudget / safeUnitPrice);

  let best = null;
  for (let back = rules.backPick; back <= requestedBack; back += 1) {
    const backCombinations = combinationCount(back, rules.backPick);
    for (let tuo = minimumTuo; tuo <= requestedTuo; tuo += 1) {
      const dantuoTickets = combinationCount(tuo, rules.frontPick - safeDan) * backCombinations;
      for (let compoundFront = minimumCompoundFront; compoundFront <= requestedCompoundFront; compoundFront += 1) {
        const compoundTickets = combinationCount(compoundFront, rules.frontPick) * backCombinations;
        const availableForSingles = paidTicketCap - dantuoTickets - compoundTickets;
        const singles = Math.min(requestedSingles, Math.floor(availableForSingles / safeMultiplier));
        if (singles < 1) continue;
        const paidTickets = dantuoTickets + compoundTickets + singles * safeMultiplier;
        const preference = (tuo / requestedTuo) + (compoundFront / requestedCompoundFront) + (back / requestedBack) + (singles / requestedSingles);
        if (!best || paidTickets > best.paidTickets || (paidTickets === best.paidTickets && preference > best.preference)) {
          best = { backCount: back, tuoCount: tuo, compoundFrontCount: compoundFront, ticketCount: singles, dantuoTickets, compoundTickets, paidTickets, preference };
        }
      }
    }
  }

  const minimumPaidTickets = 1 + (rules.frontPick + 1) + safeMultiplier;
  const minimumCost = minimumPaidTickets * safeUnitPrice;
  if (!best) {
    return { fits: false, minimumCost, cost: 0, safeDan, singleMultiplier: safeMultiplier };
  }

  return {
    fits: true,
    minimumCost,
    cost: best.paidTickets * safeUnitPrice,
    tickets: best.dantuoTickets + best.compoundTickets + best.ticketCount,
    paidTickets: best.paidTickets,
    danCount: safeDan,
    tuoCount: best.tuoCount,
    compoundFrontCount: best.compoundFrontCount,
    backCount: best.backCount,
    ticketCount: best.ticketCount,
    singleMultiplier: safeMultiplier,
    adjusted: best.tuoCount !== requestedTuo
      || best.compoundFrontCount !== requestedCompoundFront
      || best.backCount !== requestedBack
      || best.ticketCount !== requestedSingles,
  };
}
