import type { Metadata } from "next";

import { DiscoverView } from "@/features/discovery/discover-view";

export const metadata: Metadata = { title: "Results" };

// Content is private, client-fetched guest data, so instant-navigation validation is opted out.
export const instant = false;

export default function DiscoverPage() {
  return <DiscoverView />;
}
