import { describe, expect, test } from "bun:test";
import { shouldSkipForStale, shouldSkipForClose } from "../../scripts/sweep.ts";

const cutoff = new Date("2026-03-01T00:00:00Z");

// ── shouldSkipForStale ───────────────────────────────────────────

describe("shouldSkipForStale", () => {
  test("skips pull requests", () => {
    const issue = { pull_request: {}, updated_at: "2026-01-01T00:00:00Z" };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips locked issues", () => {
    const issue = { locked: true, updated_at: "2026-01-01T00:00:00Z" };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips issues with assignees", () => {
    const issue = {
      assignees: [{ login: "alice" }],
      updated_at: "2026-01-01T00:00:00Z",
    };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips recently updated issues", () => {
    const issue = { updated_at: "2026-04-01T00:00:00Z" }; // after cutoff
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips issues already labeled stale", () => {
    const issue = {
      updated_at: "2026-01-01T00:00:00Z",
      labels: [{ name: "stale" }],
    };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips issues already labeled autoclose", () => {
    const issue = {
      updated_at: "2026-01-01T00:00:00Z",
      labels: [{ name: "autoclose" }],
    };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("skips issues with enough upvotes", () => {
    const issue = {
      updated_at: "2026-01-01T00:00:00Z",
      reactions: { "+1": 10 },
    };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(true);
  });

  test("does not skip eligible issues", () => {
    const issue = {
      updated_at: "2026-01-01T00:00:00Z",
      labels: [{ name: "bug" }],
      reactions: { "+1": 2 },
    };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(false);
  });

  test("does not skip issues with no labels", () => {
    const issue = { updated_at: "2026-01-01T00:00:00Z" };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(false);
  });

  test("does not skip issues with empty assignees array", () => {
    const issue = { updated_at: "2026-01-01T00:00:00Z", assignees: [] };
    expect(shouldSkipForStale(issue, cutoff).skip).toBe(false);
  });
});

// ── shouldSkipForClose ───────────────────────────────────────────

describe("shouldSkipForClose", () => {
  test("skips pull requests", () => {
    const issue = { pull_request: {} };
    expect(shouldSkipForClose(issue, false).skip).toBe(true);
  });

  test("skips locked issues", () => {
    const issue = { locked: true };
    expect(shouldSkipForClose(issue, false).skip).toBe(true);
  });

  test("skips issues with enough upvotes", () => {
    const issue = { reactions: { "+1": 10 } };
    expect(shouldSkipForClose(issue, false).skip).toBe(true);
  });

  test("skips when there is a human comment after label", () => {
    const issue = {};
    expect(shouldSkipForClose(issue, true).skip).toBe(true);
  });

  test("does not skip eligible issues", () => {
    const issue = { reactions: { "+1": 1 } };
    expect(shouldSkipForClose(issue, false).skip).toBe(false);
  });

  test("does not skip issues with no reactions", () => {
    const issue = {};
    expect(shouldSkipForClose(issue, false).skip).toBe(false);
  });
});
