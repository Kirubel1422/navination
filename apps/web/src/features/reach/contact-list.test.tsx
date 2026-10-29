import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithLocale } from "@/test/render";
import { ContactList } from "./contact-list";

describe("ContactList", () => {
  it("offers one-tap calling to the published number, with its source", () => {
    renderWithLocale(
      <ContactList
        contacts={[
          {
            label: "ICP call centre",
            phone: "600 522222",
            tel: "tel:600522222",
            email: null,
            hours: "24/7",
            source_url: "https://icp.gov.ae/en/contact-us/",
            source_title: "Contact us",
          },
        ]}
      />,
    );
    expect(screen.getByTestId("contact-call")).toHaveAttribute("href", "tel:600522222");
    expect(screen.getByText("600 522222")).toBeInTheDocument();
    expect(screen.getByText("Listed on icp.gov.ae")).toHaveAttribute("href", "https://icp.gov.ae/en/contact-us/");
  });
});
