import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { journey } from "@/mocks/fixtures.gen";
import type { JourneyStep } from "@/lib/api/types";
import { renderWithLocale } from "@/test/render";
import { DocumentChecklist } from "./document-checklist";

const step = journey.steps.find((s) => s.checklist.length > 0) as JourneyStep;

describe("DocumentChecklist", () => {
  it("lists documents and reports the chosen status", async () => {
    const onChange = vi.fn();
    renderWithLocale(<DocumentChecklist step={step} disabled={false} onChange={onChange} />);
    const firstDoc = step.checklist[0];
    const group = screen.getByRole("group", { name: firstDoc.text });
    await userEvent.click(group.querySelector('[value="missing"]') as HTMLElement);
    expect(onChange).toHaveBeenCalledWith(firstDoc.id, "missing");
    expect(screen.getByText(/does not verify it/)).toBeInTheDocument();
  });

  it("disables changes when the plan is locked", () => {
    renderWithLocale(<DocumentChecklist step={step} disabled onChange={vi.fn()} />);
    for (const radio of screen.getAllByRole("radio")) expect(radio).toBeDisabled();
  });
});
