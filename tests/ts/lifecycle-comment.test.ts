import { describe, expect, test } from "bun:test";
import {
  buildCommentBody,
  findLifecycleEntry,
} from "../../scripts/lifecycle-comment.ts";
import { lifecycle } from "../../scripts/issue-lifecycle.ts";

describe("findLifecycleEntry", () => {
  test("finds entry by label", () => {
    const entry = findLifecycleEntry("stale");
    expect(entry?.label).toBe("stale");
    expect(entry?.days).toBe(14);
  });

  test("returns undefined for unknown label", () => {
    expect(findLifecycleEntry("no-such-label")).toBeUndefined();
  });
});

describe("buildCommentBody", () => {
  test("interpolates nudge and days", () => {
    const entry = lifecycle.find((l) => l.label === "needs-repro")!;
    const body = buildCommentBody(entry);
    expect(body).toContain(entry.nudge);
    expect(body).toContain(`${entry.days} days`);
  });

  test("body ends with the auto-close warning", () => {
    for (const entry of lifecycle) {
      const body = buildCommentBody(entry);
      expect(body).toContain(
        `closed automatically if there's no activity within ${entry.days} days`
      );
    }
  });

  test("body starts with the entry's nudge", () => {
    for (const entry of lifecycle) {
      const body = buildCommentBody(entry);
      expect(body.startsWith(entry.nudge)).toBe(true);
    }
  });
});
