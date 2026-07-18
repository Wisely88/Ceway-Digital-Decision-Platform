let sequence = 0;

export function createRecordId(prefix, now = Date.now, randomUuid = globalThis.crypto?.randomUUID?.bind(globalThis.crypto)) {
  if (randomUuid) return `${prefix}-${randomUuid()}`;
  sequence = (sequence + 1) % Number.MAX_SAFE_INTEGER;
  return `${prefix}-${now()}-${sequence}`;
}
