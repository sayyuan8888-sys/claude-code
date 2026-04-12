import { describe, expect, test } from "bun:test";
import {
  extractDuplicateIssueNumber,
  shouldAutoClose,
  type AutoCloseInput,
} from "../../scripts/auto-close-duplicates.ts";

// ── extractDuplicateIssueNumber ──────────────────────────────────

describe("extractDuplicateIssueNumber", () => {
  test("extracts issue number from #123 format", () => {
    expect(extractDuplicateIssueNumber("Duplicate of #456")).toBe(456);
  });

  test("extracts issue number from GitHub URL", () => {
    expect(
      extractDuplicateIssueNumber(
        "See https://github.com/anthropics/claude-code/issues/789"
      )
    ).toBe(789);
  });

  test("returns null when no issue reference found", () => {
    expect(extractDuplicateIssueNumber("No reference here")).toBeNull();
  });

  test("returns first match when multiple #refs present", () => {
    expect(extractDuplicateIssueNumber("See #100 and #200")).toBe(100);
  });

  test("handles #0", () => {
    expect(extractDuplicateIssueNumber("Issue #0")).toBe(0);
  });

  test("returns null for non-numeric after #", () => {
    expect(extractDuplicateIssueNumber("Use #hashtag")).toBeNull();
  });

  test("extracts from realistic duplicate comment body", () => {
    const body =
      "Found 1 possible duplicate issue:\n\n1. https://github.com/anthropics/claude-code/issues/42\n\nThis issue will be automatically closed.";
    expect(extractDuplicateIssueNumber(body)).toBe(42);
  });
});

// ── shouldAutoClose ──────────────────────────────────────────────

const baseIssue = {
  number: 10,
  title: "Test issue",
  user: { id: 1 },
  created_at: "2026-01-01T00:00:00Z",
};

const makeDupeComment = (
  daysAgo: number,
  id = 100
) => ({
  id,
  body: "Found 1 possible duplicate issue:\n\n1. #42",
  created_at: new Date(
    Date.now() - daysAgo * 86400000
  ).toISOString(),
  user: { type: "Bot", id: 999 },
});

const threeDaysAgo = new Date(Date.now() - 3 * 86400000);

describe("shouldAutoClose", () => {
  test("skips when no duplicate comments exist", () => {
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("no duplicate comments");
  });

  test("skips when duplicate comment is too recent", () => {
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [makeDupeComment(1)], // 1 day ago = too recent
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("too recent");
  });

  test("skips when there are comments after duplicate detection", () => {
    const dupeComment = makeDupeComment(5);
    const laterComment = {
      id: 200,
      body: "Not a dupe!",
      created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
      user: { type: "User", id: 2 },
    };
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [dupeComment, laterComment],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("activity after");
  });

  test("skips when author thumbs-downed the duplicate comment", () => {
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [makeDupeComment(5)],
      reactions: [{ user: { id: 1 }, content: "-1" }], // same user id as issue author
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("disagreed");
  });

  test("skips when duplicate issue number cannot be extracted", () => {
    const badComment = {
      ...makeDupeComment(5),
      body: "Found 1 possible duplicate issue:\n\nNo number here",
    };
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [badComment],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("could not extract");
  });

  test("returns shouldClose=true for valid duplicate", () => {
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [makeDupeComment(5)],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(true);
    expect(result.duplicateOf).toBe(42);
  });

  test("ignores non-bot duplicate comments", () => {
    const humanComment = {
      id: 100,
      body: "Found 1 possible duplicate issue:\n\n1. #42",
      created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
      user: { type: "User", id: 2 },
    };
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [humanComment],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(false);
    expect(result.reason).toContain("no duplicate comments");
  });

  test("uses last duplicate comment when multiple exist", () => {
    const older = {
      ...makeDupeComment(10, 100),
      body: "Found 1 possible duplicate issue:\n\n1. #99",
    };
    const newer = {
      ...makeDupeComment(5, 200),
      body: "Found 1 possible duplicate issue:\n\n1. #42",
    };
    const result = shouldAutoClose({
      issue: baseIssue,
      comments: [older, newer],
      reactions: [],
      threeDaysAgo,
    });
    expect(result.shouldClose).toBe(true);
    expect(result.duplicateOf).toBe(42);
  });
});
