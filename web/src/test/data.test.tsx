import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import DataPipeline from "@/pages/DataPipeline";
import { mockApi, renderWithProviders } from "./utils";

const routes = () => ({
  "/api/analysis/run": [202, { status: "running", stage: "Starting", dataset_loaded: false }],
  "/api/analysis/status": { status: "idle", stage: "", dataset_loaded: false },
  "/api/analysis/ingest": { available: false },
  "/api/analysis/rejects": { items: [], meta: { page: 1, page_size: 10, total: 0, total_pages: 1 } },
  "/api/analysis/config": { rules: [{ code: "STRUCTURING", description: "d", weight: 0.5 }], thresholds: {}, score_disclaimer: "x", score_formula: "f" },
  "/api/dataset": { loaded: false, ignored_columns: [], notes: [] },
});
const runCall = (f: ReturnType<typeof mockApi>) => f.mock.calls.find((c) => String(c[0]).includes("/api/analysis/run"));

describe("Data & Pipeline: synthetic run options", () => {
  it("sends include_structuring=false by default", async () => {
    const f = mockApi(routes());
    renderWithProviders(<DataPipeline />);
    await userEvent.click(await screen.findByRole("button", { name: /Generate & analyse/ }));
    await waitFor(() => expect(runCall(f)).toBeTruthy());
    expect(JSON.parse(String((runCall(f)![1] as RequestInit).body))).toMatchObject({ source: "synthetic", include_structuring: false });
  });
  it("sends include_structuring=true when the toggle is on, and enforces >= 30 accounts", async () => {
    const f = mockApi(routes());
    renderWithProviders(<DataPipeline />);
    await userEvent.click(await screen.findByRole("switch", { name: /STRUCTURING scenario/ }));
    const accounts = screen.getByLabelText("Number of accounts");
    await userEvent.clear(accounts); await userEvent.type(accounts, "25");
    expect(screen.getByRole("button", { name: /Generate & analyse/ })).toBeDisabled();
    await userEvent.clear(accounts); await userEvent.type(accounts, "60");
    await userEvent.click(screen.getByRole("button", { name: /Generate & analyse/ }));
    await waitFor(() => expect(runCall(f)).toBeTruthy());
    expect(JSON.parse(String((runCall(f)![1] as RequestInit).body))).toMatchObject({ num_accounts: 60, include_structuring: true });
  });
});
