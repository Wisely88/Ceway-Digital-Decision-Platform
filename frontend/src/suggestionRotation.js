export function rotateItems(items, variant = 0) {
  if (!items.length) return [];
  const shift = Math.abs(Number(variant) || 0) % items.length;
  return [...items.slice(shift), ...items.slice(0, shift)];
}

export function topScoreNumbers(rows, max, variant = 0) {
  const ranked = [...(rows || [])]
    .sort((left, right) => (right.total_score || 0) - (left.total_score || 0))
    .map((row) => Number(row.number))
    .filter((number) => number >= 1 && number <= max);
  const fallback = Array.from({ length: max }, (_, index) => index + 1);
  const completeRanked = [...new Set([...ranked, ...fallback])];
  if (!variant || completeRanked.length < 3) return completeRanked;

  const bandSize = Math.min(completeRanked.length, Math.max(8, Math.ceil(completeRanked.length * 0.4)));
  const candidateBand = completeRanked.slice(0, bandSize);
  const start = (Number(variant) * 2) % bandSize;
  const strideOptions = [3, 5, 7, 11];
  const stride = strideOptions[Math.abs(Number(variant) - 1) % strideOptions.length];
  const varied = [];
  for (let offset = 0; offset < bandSize; offset += 1) {
    const candidate = candidateBand[(start + offset * stride) % bandSize];
    if (!varied.includes(candidate)) varied.push(candidate);
  }
  candidateBand.forEach((number) => {
    if (!varied.includes(number)) varied.push(number);
  });
  completeRanked.forEach((number) => {
    if (!varied.includes(number)) varied.push(number);
  });
  return varied;
}

function combinations(items, pick, start = 0, prefix = [], output = []) {
  if (prefix.length === pick) {
    output.push([...prefix]);
    return output;
  }
  for (let index = start; index <= items.length - (pick - prefix.length); index += 1) {
    prefix.push(items[index]);
    combinations(items, pick, index + 1, prefix, output);
    prefix.pop();
  }
  return output;
}

export function hasConsecutiveNumbers(numbers) {
  const sorted = [...numbers].map(Number).sort((left, right) => left - right);
  return sorted.some((number, index) => index > 0 && number - sorted[index - 1] === 1);
}

export function selectScoredCombination(rows, max, pick, variant = 1, excludedNumbers = [], options = {}) {
  const safePick = Math.max(1, Math.min(Number(pick) || 1, max));
  const excluded = new Set((excludedNumbers || []).map(Number));
  const scoreByNumber = new Map(
    (rows || []).map((row) => [Number(row.number), Number(row.total_score ?? row.score ?? 0)]),
  );
  const ranked = Array.from({ length: max }, (_, index) => index + 1)
    .filter((number) => !excluded.has(number))
    .sort((left, right) => (scoreByNumber.get(right) || 0) - (scoreByNumber.get(left) || 0) || left - right);
  const effectivePick = Math.min(safePick, ranked.length);
  const bandSize = Math.min(ranked.length, effectivePick + 4);
  const candidateBand = ranked.slice(0, bandSize);
  const candidates = combinations(candidateBand, effectivePick)
    .map((numbers) => ({
      numbers,
      score: numbers.reduce((sum, number) => sum + (scoreByNumber.get(number) || 0), 0),
    }))
    .sort((left, right) => right.score - left.score || left.numbers.join("-").localeCompare(right.numbers.join("-")));
  if (!candidates.length) return ranked.slice(0, effectivePick);
  const preferred = options.avoidConsecutive
    ? candidates.filter((candidate) => !hasConsecutiveNumbers(candidate.numbers))
    : candidates;
  const selectable = preferred.length ? preferred : candidates;
  const index = (Math.max(1, Math.floor(Number(variant) || 1)) - 1) % selectable.length;
  return selectable[index].numbers;
}
