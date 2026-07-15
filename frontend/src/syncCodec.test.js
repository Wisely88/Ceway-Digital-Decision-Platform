import test from "node:test";
import assert from "node:assert/strict";
import { decodeSyncBundle, encodeSyncBundle } from "./syncCodec.js";

test("sync bundle preserves Chinese plan data", () => {
  const records = [{ id: "1", strategy: "balanced", plan: { mode: "single", reason: "均衡方案" } }];
  const code = encodeSyncBundle("DLT", records);
  const decoded = decodeSyncBundle(code, "DLT");
  assert.equal(decoded.scene, "DLT");
  assert.deepEqual(decoded.records, records);
});

test("sync bundle rejects a different scene", () => {
  const code = encodeSyncBundle("SSQ", []);
  assert.throws(() => decodeSyncBundle(code, "DLT"), /对应场景/);
});

test("sync bundle rejects damaged input", () => {
  assert.throws(() => decodeSyncBundle("CEWAY1.invalid", "DLT"), /损坏/);
});

test("sync bundle rejects oversized input", () => {
  assert.throws(() => decodeSyncBundle(`CEWAY1.${"a".repeat(2_000_001)}`, "DLT"), /大小上限/);
});
