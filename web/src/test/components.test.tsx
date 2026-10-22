import { fireEvent, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApiError } from "@/api/client";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Field, Input, Segmented } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { ErrorState } from "@/components/ui/States";
import { SeverityBadge } from "@/components/domain/badges";
import { RequireDataset } from "@/components/domain/RequireDataset";
import { mockApi, renderWithProviders } from "./utils";

describe("Pagination", () => {
  it("disables Previous on the first page and navigates forward", async () => {
    const onPage = vi.fn();
    renderWithProviders(<Pagination meta={{ page: 1, page_size: 25, total: 60, total_pages: 3 }} onPage={onPage} />);
    expect(screen.getByLabelText("Previous page")).toBeDisabled();
    expect(screen.getByText(/1–25 of 60/)).toBeInTheDocument();
    await userEvent.click(screen.getByLabelText("Next page")); expect(onPage).toHaveBeenCalledWith(2);
  });
  it("shows 0–0 for an empty result", () => {
    renderWithProviders(<Pagination meta={{ page: 1, page_size: 25, total: 0, total_pages: 1 }} onPage={() => {}} />);
    expect(screen.getByText(/0–0 of 0/)).toBeInTheDocument();
  });
});

describe("ErrorState", () => {
  it("explains an unreachable backend and offers retry", async () => {
    const retry = vi.fn();
    renderWithProviders(<ErrorState error={new ApiError(0, "NETWORK_ERROR", "Cannot reach the API.")} onRetry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Backend unreachable");
    await userEvent.click(screen.getByRole("button", { name: "Retry" })); expect(retry).toHaveBeenCalled();
  });
});

describe("ConfirmDialog", () => {
  it("cancels on Escape and confirms on click; nothing renders when closed", async () => {
    const onCancel = vi.fn(), onConfirm = vi.fn();
    const { rerender } = renderWithProviders(<ConfirmDialog open title="Close this alert?" onCancel={onCancel} onConfirm={onConfirm} />);
    expect(screen.getByRole("alertdialog")).toHaveTextContent("Close this alert?");
    fireEvent.keyDown(window, { key: "Escape" }); expect(onCancel).toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Confirm" })); expect(onConfirm).toHaveBeenCalled();
    rerender(<ConfirmDialog open={false} title="x" onCancel={onCancel} onConfirm={onConfirm} />);
  });
  it("can disable confirm until a required choice is made", () => {
    renderWithProviders(<ConfirmDialog open confirmDisabled title="t" onCancel={() => {}} onConfirm={() => {}} />);
    expect(screen.getByRole("button", { name: "Confirm" })).toBeDisabled();
  });
});

describe("SeverityBadge", () => {
  it("renders the label, and a dash when absent", () => {
    const { rerender } = renderWithProviders(<SeverityBadge severity="critical" />);
    expect(screen.getByText("Critical")).toBeInTheDocument();
    rerender(<SeverityBadge severity={null} />); expect(screen.getByText("—")).toBeInTheDocument();
  });
});

describe("RequireDataset (first-run, loading and error states)", () => {
  const dsEmpty = { loaded: false, ignored_columns: [], notes: [] };
  it("shows the first-run call to action when no dataset is loaded", async () => {
    mockApi({ "/api/dataset": dsEmpty, "/api/analysis/status": { status: "idle", stage: "", dataset_loaded: false } });
    renderWithProviders(<RequireDataset><p>secret page</p></RequireDataset>);
    expect(await screen.findByText("No dataset loaded yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Generate synthetic dataset/ })).toBeInTheDocument();
    expect(screen.queryByText("secret page")).not.toBeInTheDocument();
  });
  it("renders children once a dataset exists", async () => {
    mockApi({ "/api/dataset": { loaded: true, ignored_columns: [], notes: [] }, "/api/analysis/status": { status: "completed", stage: "Done", dataset_loaded: true } });
    renderWithProviders(<RequireDataset><p>secret page</p></RequireDataset>);
    expect(await screen.findByText("secret page")).toBeInTheDocument();
  });
  it("shows an API error state instead of a blank page", async () => {
    mockApi({ "/api/dataset": [500, { error: { code: "INTERNAL_ERROR", message: "An unexpected error occurred." } }] });
    renderWithProviders(<RequireDataset><p>x</p></RequireDataset>);
    expect(await screen.findByRole("alert")).toHaveTextContent("unexpected error");
  });
});

describe("Field / Segmented accessibility", () => {
  it("every option of a segmented control keeps its own accessible name (label must not rename the first radio)", () => {
    renderWithProviders(
      <Field label="Colour by" group><Segmented label="Colour mode" value="risk" onChange={() => {}} options={[{ value: "risk", label: "Risk" }, { value: "community", label: "Community" }]} /></Field>,
    );
    expect(screen.getByRole("radio", { name: "Risk" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Community" })).not.toBeChecked();
    expect(screen.getByRole("group", { name: "Colour by" })).toBeInTheDocument();
    expect(screen.getByRole("radiogroup", { name: "Colour mode" })).toBeInTheDocument();
    expect(screen.getAllByRole("radio")).toHaveLength(2);
    expect(screen.queryByRole("radio", { name: /Colour by/ })).toBeNull(); // the label must not rename an option
  });
  it("a plain Field still labels its single input", () => {
    renderWithProviders(<Field label="Seed"><Input /></Field>);
    expect(screen.getByLabelText("Seed")).toBeInTheDocument();
  });
});
