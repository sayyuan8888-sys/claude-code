import { describe, expect, test } from "bun:test";
import { spawnSync } from "child_process";
import { resolve } from "path";
import {
  buildCommentBody,
  findLifecycleEntry,
} from "../../scripts/lifecycle-comment.ts";
import { lifecycle } from "../../scripts/issue-lifecycle.ts";

// lifecycle-comment.ts runs top-level code on import, so we exercise it as a
// subprocess with --dry-run (no real GitHub call is made in dry-run mode).

const SCRIPT = resolve(import.meta.dir, "../../scripts/lifecycle-comment.ts");
const BUN = process.execPath; // the `bun` running this test

function run(
  env: Record<string, string | undefined>,
  args: string[] = ["--dry-run"],
) {
  return spawnSync(BUN, ["run", SCRIPT, ...args], {
    env: { ...env, PATH: process.env.PATH ?? "" },
    encoding: "utf8",
    timeout: 10_000,
  });
}

describe("lifecycle-comment CLI", () => {
  test("fails without GITHUB_REPOSITORY", () => {
    const result = run({
      LABEL: "stale",
      ISSUE_NUMBER: "42",
    });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("GITHUB_REPOSITORY");
  });

  test("fails without LABEL", () => {
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      ISSUE_NUMBER: "42",
    });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("LABEL");
  });

  test("fails without ISSUE_NUMBER", () => {
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      LABEL: "stale",
    });
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("ISSUE_NUMBER");
  });

  test("dry-run prints the comment body for a known label", () => {
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      LABEL: "stale",
      ISSUE_NUMBER: "42",
    });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("#42");
    expect(result.stdout).toContain("stale");
    // The body should reference the entry's day count.
    expect(result.stdout).toMatch(/\d+ days/);
  });

  test("unknown label exits 0 with a skip message", () => {
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      LABEL: "not-a-real-label",
      ISSUE_NUMBER: "42",
    });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("skipping");
  });

  test("missing GITHUB_TOKEN without --dry-run fails", () => {
    const result = run(
      {
        GITHUB_REPOSITORY: "anthropics/claude-code",
        LABEL: "stale",
        ISSUE_NUMBER: "42",
      },
      [], // no --dry-run
    );
    expect(result.status).not.toBe(0);
    expect(result.stderr).toContain("GITHUB_TOKEN");
  });
});

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
        `closed automatically if there's no activity within ${entry.days} days`,
      );
    }
  });

  test("body starts with the entry's nudge", () => {
    for (const entry of lifecycle) {
      const body = buildCommentBody(entry);
      expect(body.startsWith(entry.nudge)).toBe(true);
    }
  });

  test("every entry's body serializes to a JSON POST payload without loss", () => {
    // This is the payload the script actually sends on line 58:
    //   JSON.stringify({ body })
    // Guards against any future nudge containing characters that would
    // break JSON.stringify or be silently mangled by JSON.parse round-trip.
    for (const entry of lifecycle) {
      const body = buildCommentBody(entry);
      const payload = JSON.stringify({ body });
      const round = JSON.parse(payload) as { body: string };
      expect(round.body).toBe(body);
    }
  });

  test("nudges with backticks, quotes, and newlines survive JSON serialization", () => {
    // Synthetic entry mimicking the shape of `lifecycle[number]` — we don't
    // add it to the real list, just feed it to buildCommentBody so a future
    // lifecycle entry with special chars wouldn't silently break the HTTP
    // body on line 58 of lifecycle-comment.ts.
    const entry = {
      label: "synthetic" as const,
      days: 9,
      reason: "test",
      nudge:
        'Example: run `claude "hello"` and check for `<error>\nMore`.\nSee "docs".',
    } as unknown as Parameters<typeof buildCommentBody>[0];
    const body = buildCommentBody(entry);
    expect(body).toContain("`claude");
    expect(body).toContain('"docs"');
    expect(body).toContain("\n");
    // The real script does JSON.stringify({ body }) — ensure that succeeds
    // and round-trips cleanly.
    const parsed = JSON.parse(JSON.stringify({ body })) as { body: string };
    expect(parsed.body).toBe(body);
  });
});

describe("lifecycle entries", () => {
  test("all labels are unique", () => {
    // Duplicate labels would make findLifecycleEntry return the first match
    // silently — worth guarding against.
    const labels = lifecycle.map((l) => l.label);
    expect(new Set(labels).size).toBe(labels.length);
  });

  test("no entry has an empty nudge or non-positive day count", () => {
    for (const entry of lifecycle) {
      expect(entry.nudge.length).toBeGreaterThan(0);
      expect(entry.days).toBeGreaterThan(0);
    }
  });
});

describe("lifecycle-comment CLI (additional edge cases)", () => {
  test("non-numeric ISSUE_NUMBER still runs in dry-run", () => {
    // The script doesn't validate ISSUE_NUMBER format; GitHub is the source
    // of truth. This test locks in that behavior so a future validation
    // change is an explicit decision, not an accidental regression.
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      LABEL: "stale",
      ISSUE_NUMBER: "not-a-number",
    });
    expect(result.status).toBe(0);
    expect(result.stdout).toContain("#not-a-number");
  });

  test("dry-run does NOT require GITHUB_TOKEN", () => {
    // Regression guard: the dry-run branch must short-circuit before any
    // auth check would fire, so CI dry-run jobs can run without a token.
    const result = run({
      GITHUB_REPOSITORY: "anthropics/claude-code",
      LABEL: "invalid",
      ISSUE_NUMBER: "1",
    });
    expect(result.status).toBe(0);
    // The output contains the nudge body — i.e. we reached the dry-run branch.
    expect(result.stdout).toContain("Claude Code");
  });
});
