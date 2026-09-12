import { describe, expect, it } from "vitest";

import { formatNumber, titleCase } from "./format";

describe("format helpers", () => {
  it("formats numbers with grouping", () => {
    expect(formatNumber(1234567)).toBe((1234567).toLocaleString());
    expect(formatNumber(null)).toBe("—");
  });

  it("title-cases snake/kebab strings", () => {
    expect(titleCase("weak_algorithm_detected")).toBe("Weak Algorithm Detected");
    expect(titleCase("ocsp-stale")).toBe("Ocsp Stale");
  });
});
