import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { renderWithLocale } from "@/test/render";
import { AgentActivity } from "./agent-activity";

describe("AgentActivity", () => {
  it("lists the tools the agent used with readable names", async () => {
    renderWithLocale(
      <AgentActivity
        steps={[
          { tool: "list_catalog_services", detail: "10 reviewed services" },
          { tool: "fetch_official_page", detail: "https://u.ae/en/x" },
        ]}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: /How the AI agent worked \(2 steps\)/ }));
    expect(screen.getByText(/Read official page/)).toBeInTheDocument();
    expect(screen.getByText("https://u.ae/en/x")).toBeInTheDocument();
  });

  it("renders nothing without steps", () => {
    const { container } = renderWithLocale(<AgentActivity steps={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
