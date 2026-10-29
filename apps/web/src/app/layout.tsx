import type { Metadata, Viewport } from "next";
import { Readex_Pro } from "next/font/google";

import { AppShell } from "@/components/layout/app-shell";
import { localeBootScript } from "@/lib/i18n/locale";
import "./globals.css";
import { Providers } from "./providers";

// One family for both scripts: Readex Pro pairs Arabic with Lexend's readability-tuned Latin.
// The HEXP (width) axis lets headlines run expanded while body text stays at normal width.
const readex = Readex_Pro({
  subsets: ["latin", "arabic"],
  axes: ["HEXP"],
  variable: "--font-readex",
  display: "swap",
});

export const metadata: Metadata = {
  title: { default: "NaviNation", template: "%s · NaviNation" },
  description:
    "NaviNation helps citizens and residents go from an everyday need to reviewed UAE government services, with sources, a step plan and an honest coach.",
  applicationName: "NaviNation",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0e6170",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" dir="ltr" className={readex.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: localeBootScript }} />
      </head>
      <body className="flex min-h-dvh flex-col antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
