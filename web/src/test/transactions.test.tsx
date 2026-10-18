import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import Transactions from "@/pages/Transactions";
import { mockApi, renderWithProviders } from "./utils";

const row = (i: number) => ({ transaction_id: `TXN${i}`, sender_account_id: "ACC00001", receiver_account_id: "ACC00002", amount_inr: 2500000 + i,
  timestamp: "2024-01-14T12:58:00+05:30", transaction_type: "RTGS", sender_risk: 54.4, receiver_risk: 12, flagged_rules: ["LARGE_AMOUNT"] });
const meta = (total: number) => ({ page: 1, page_size: 25, total, total_pages: 1 });

describe("Transactions page", () => {
  it("renders INR amounts, IST times and rule badges from the API", async () => {
    mockApi({ "/api/transactions": { items: [row(1), row(2)], meta: meta(2) } });
    renderWithProviders(<Transactions />);
    expect(await screen.findByText("TXN1")).toBeInTheDocument();
    expect(screen.getByText("₹25,00,001.00")).toBeInTheDocument();
    expect(screen.getAllByText("14 Jan 2024, 12:58 IST").length).toBe(2);
    expect(screen.getAllByText("LARGE_AMOUNT").length).toBe(2);
  });
  it("sends filters to the backend", async () => {
    const f = mockApi({ "/api/transactions": { items: [row(1)], meta: meta(1) } });
    renderWithProviders(<Transactions />);
    await screen.findByText("TXN1");
    await userEvent.type(screen.getByLabelText("Minimum amount"), "1000000");
    await waitFor(() => expect(f.mock.calls.some((c) => String(c[0]).includes("min_amount=1000000"))).toBe(true), { timeout: 2000 });
  });
  it("shows a no-results state with a way out", async () => {
    mockApi({ "/api/transactions": { items: [], meta: meta(0) } });
    renderWithProviders(<Transactions />);
    expect(await screen.findByText("No transactions match")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Clear filters" }).length).toBeGreaterThan(0);
  });
  it("surfaces a server-side invalid-filter error", async () => {
    mockApi({ "/api/transactions": [422, { error: { code: "INVALID_FILTER", message: "min_amount cannot exceed max_amount." } }] });
    renderWithProviders(<Transactions />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid filter");
    expect(screen.getByRole("alert")).toHaveTextContent("min_amount cannot exceed max_amount.");
  });
  it("shows a backend-unreachable error", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new TypeError("x"); }));
    renderWithProviders(<Transactions />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Backend unreachable");
  });
  it("shows a loading skeleton before data arrives", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    renderWithProviders(<Transactions />);
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
  });
});
