import { describe, expect, test } from "bun:test";
import { lifecycle, STALE_UPVOTE_THRESHOLD } from "../../scripts/issue-lifecycle.ts";

describe("lifecycle data", () => {
  test("has exactly 5 entries in expected order", () => {
    expect(lifecycle.map((e) => e.label)).toEqual([
      "invalid",
      "needs-repro",
      "needs-info",
      "stale",
      "autoclose",
    ]);
  });

  test("every entry has non-empty label, nudge, reason", () => {
    for (const entry of lifecycle) {
      expect(entry.label.length).toBeGreaterThan(0);
      expect(entry.nudge.length).toBeGreaterThan(0);
      expect(entry.reason.length).toBeGreaterThan(0);
    }
  });

  test("every entry has positive days", () => {
    for (const entry of lifecycle) {
      expect(entry.days).toBeGreaterThan(0);
    }
  });

  test("stale and autoclose both use 14 days", () => {
    const stale = lifecycle.find((e) => e.label === "stale");
    const autoclose = lifecycle.find((e) => e.label === "autoclose");
    expect(stale?.days).toBe(14);
    expect(autoclose?.days).toBe(14);
  });

  test("all labels are unique", () => {
    const labels = lifecycle.map((e) => e.label);
    expect(new Set(labels).size).toBe(labels.length);
  });
});

describe("STALE_UPVOTE_THRESHOLD", () => {
  test("is 10", () => {
    expect(STALE_UPVOTE_THRESHOLD).toBe(10);
  });
});
