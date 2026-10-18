import { dateOnly, dayToIso, dt, inr, inrCompact, int } from "@/lib/format";

describe("INR formatting", () => {
  it("uses Indian digit grouping with two decimals", () => { expect(inr(2854377.49)).toBe("₹28,54,377.49"); });
  it("compacts to lakh and crore", () => {
    expect(inrCompact(2_500_000)).toBe("₹25.00 L");
    expect(inrCompact(28_543_777)).toBe("₹2.85 Cr");
    expect(inrCompact(9_500)).toBe("₹9,500");
  });
  it("renders a dash for missing or non-finite values", () => { expect(inr(null)).toBe("—"); expect(inr(Infinity)).toBe("—"); expect(int(undefined)).toBe("—"); });
});
describe("IST formatting", () => {
  it("converts UTC instants to IST (+05:30)", () => { expect(dt("2024-01-01T00:00:00+00:00")).toBe("01 Jan 2024, 05:30 IST"); });
  it("keeps IST offsets as-is", () => { expect(dt("2024-03-01T10:15:00+05:30")).toBe("01 Mar 2024, 10:15 IST"); });
  it("handles an IST date across a UTC day boundary", () => { expect(dateOnly("2024-01-01T20:00:00+00:00")).toBe("02 Jan 2024"); });
  it("is safe on bad input", () => { expect(dt("nonsense")).toBe("—"); expect(dt(null)).toBe("—"); });
  it("builds IST day bounds for filters", () => {
    expect(dayToIso("2024-01-02")).toBe("2024-01-02T00:00:00+05:30");
    expect(dayToIso("2024-01-02", true)).toBe("2024-01-02T23:59:59+05:30");
    expect(dayToIso("")).toBeUndefined();
  });
});
