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
  return rotateItems([...new Set([...ranked, ...fallback])], variant);
}

