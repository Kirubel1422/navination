import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithLocale } from "@/test/render";
import { RelevanceBadge, UnconfirmedValue, VerificationBadge } from "./badges";

describe("status badges", () => {
  it("convey relevance with text, not colour alone", () => {
    renderWithLocale(<RelevanceBadge relevance="criterion_mismatch" />);
    expect(screen.getByText("May not match your profile")).toBeInTheDocument();
  });

  it("label needs-review and demo records", () => {
    renderWithLocale(
      <>
        <VerificationBadge status="needs_review" />
        <VerificationBadge status="demo" />
      </>,
    );
    expect(screen.getByText(/Needs review/)).toBeInTheDocument();
    expect(screen.getByText(/Demo record/)).toBeInTheDocument();
  });

  it("shows unconfirmed values explicitly, in Arabic too", () => {
    renderWithLocale(<UnconfirmedValue />, "ar");
    expect(screen.getByText("غير مؤكد في مصادرنا")).toBeInTheDocument();
  });
});

describe("origin badge", () => {
  it("labels AI-found services and stays silent for catalog ones", async () => {
    const { OriginBadge } = await import("./badges");
    renderWithLocale(
      <>
        <OriginBadge origin="ai_web" />
        <OriginBadge origin="catalog" />
      </>,
    );
    expect(screen.getAllByTestId("origin-ai-web")).toHaveLength(1);
    expect(screen.getByText(/From an official website, not reviewed yet/)).toBeInTheDocument();
  });
});
