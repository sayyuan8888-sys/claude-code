import { describe, expect, test } from "bun:test";
import {
  lifecycle,
  STALE_UPVOTE_THRESHOLD,
  type LifecycleLabel,
} from "../../scripts/issue-lifecycle.ts";

// This module is the single source of truth consumed by sweep.ts,
// lifecycle-comment.ts, and auto-close-duplicates.ts. A shape regression here
// silently breaks every consumer.

describe("lifecycle array", () => {
  test("is non-empty", () => {
    expect(lifecycle.length).toBeGreaterThan(0);
  });

  test("every entry has required fields with correct types", () => {
    for (const entry of lifecycle) {
      expect(typeof entry.label).toBe("string");
      expect(entry.label.length).toBeGreaterThan(0);
      expect(typeof entry.days).toBe("number");
      expect(entry.days).toBeGreaterThan(0);
      expect(Number.isInteger(entry.days)).toBe(true);
      expect(typeof entry.reason).toBe("string");
      expect(entry.reason.length).toBeGreaterThan(0);
      expect(typeof entry.nudge).toBe("string");
      expect(entry.nudge.length).toBeGreaterThan(0);
    }
  });

  test("labels are unique", () => {
    const labels = lifecycle.map((l) => l.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  test("includes the terminal labels consumers depend on", () => {
    // sweep.ts and auto-close-duplicates.ts rely on these specific labels.
    const labels = lifecycle.map((l) => l.label);
    expect(labels).toContain("stale");
    expect(labels).toContain("autoclose");
  });
});

describe("STALE_UPVOTE_THRESHOLD", () => {
  test("is a positive integer", () => {
    expect(typeof STALE_UPVOTE_THRESHOLD).toBe("number");
    expect(Number.isInteger(STALE_UPVOTE_THRESHOLD)).toBe(true);
    expect(STALE_UPVOTE_THRESHOLD).toBeGreaterThan(0);
  });
});

describe("LifecycleLabel type covers every array label", () => {
  test("every label narrows to LifecycleLabel", () => {
    // Purely a compile-time check: this block must type-check.
    for (const entry of lifecycle) {
      const label: LifecycleLabel = entry.label;
      expect(typeof label).toBe("string");
    }
  });
});
