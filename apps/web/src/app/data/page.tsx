import type { Metadata } from "next";

import { DataView } from "@/features/opendata/data-view";

export const metadata: Metadata = { title: "Open data" };

// Live portal status and the published navigation dataset are fetched in the browser.
export const instant = false;

export default function DataPage() {
  return <DataView />;
}
