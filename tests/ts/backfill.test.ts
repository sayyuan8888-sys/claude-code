import { describe, expect, test } from "bun:test";
import { shouldStopPagination, type PaginationInput } from "../../scripts/backfill-duplicate-comments.ts";

describe("shouldStopPagination", () => {
  const base: PaginationInput = {
    oldestIssueNumber: 100,
    minIssueNumber: 50,
    maxIssueNumber: 200,
    page: 1,
    pageLimit: 200,
    filteredCount: 10,
    pageCount: 100,
  };

  test("stops when oldest issue is below minimum", () => {
    const result = shouldStopPagination({ ...base, oldestIssueNumber: 30 });
    expect(result.stop).toBe(true);
    expect(result.reason).toContain("below minimum");
  });

  test("stops when page exceeds limit", () => {
    const result = shouldStopPagination({ ...base, page: 201, pageLimit: 200 });
    expect(result.stop).toBe(true);
    expect(result.reason).toContain("page limit");
  });

  test("continues when oldest issue is within range", () => {
    const result = shouldStopPagination({ ...base, oldestIssueNumber: 100 });
    expect(result.stop).toBe(false);
  });

  test("continues when oldest issue is above max (haven't reached range)", () => {
    const result = shouldStopPagination({ ...base, oldestIssueNumber: 250 });
    expect(result.stop).toBe(false);
  });

  test("continues when oldest issue is at minimum boundary", () => {
    const result = shouldStopPagination({ ...base, oldestIssueNumber: 50 });
    expect(result.stop).toBe(false);
  });

  test("continues when oldest is undefined (empty page handled elsewhere)", () => {
    const result = shouldStopPagination({ ...base, oldestIssueNumber: undefined });
    expect(result.stop).toBe(false);
  });
});
