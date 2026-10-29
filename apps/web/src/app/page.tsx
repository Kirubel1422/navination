import { HomeView } from "@/features/discovery/home-view";

// Content is private, client-fetched guest data, so instant-navigation validation is opted out.
export const instant = false;

export default function HomePage() {
  return <HomeView />;
}
