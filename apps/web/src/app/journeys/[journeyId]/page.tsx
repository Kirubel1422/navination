import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { JourneyView } from "@/features/journey/journey-view";

// Content is private, client-fetched guest data, so instant-navigation validation is opted out.
export const instant = false;

export const metadata: Metadata = { title: "My plan" };

export default function JourneyPage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <JourneyView />
    </Suspense>
  );
}
