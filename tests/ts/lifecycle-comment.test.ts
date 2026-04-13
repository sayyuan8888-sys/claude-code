import { describe, expect, test } from "bun:test";
import { spawnSync } from "child_process";
import { resolve } from "path";

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
