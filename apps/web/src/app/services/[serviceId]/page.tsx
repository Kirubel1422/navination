import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ServiceDetailView } from "@/features/services/service-detail-view";

// Content is private, client-fetched guest data, so instant-navigation validation is opted out.
export const instant = false;

export const metadata: Metadata = { title: "Service details" };

export default function ServicePage() {
  return (
    <Suspense fallback={<Skeleton className="h-64 w-full" />}>
      <ServiceDetailView />
    </Suspense>
  );
}
