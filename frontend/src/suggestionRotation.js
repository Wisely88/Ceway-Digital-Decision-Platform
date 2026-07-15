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
