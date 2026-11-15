import type { Metadata, Viewport } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import TabBar from "@/components/TabBar";
import TopBar from "@/components/TopBar";

export const metadata: Metadata = {
  title: "FINN",
  description: "A financial investment agent that shows you only what matters.",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
  appleWebApp: { capable: true, title: "FINN", statusBarStyle: "default" },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, maximumScale: 1, viewportFit: "cover", themeColor: "#f6f6f4" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-dvh">
        <StoreProvider>
          <div className="mx-auto max-w-[520px] min-h-dvh flex flex-col">
            <TopBar />
            <main className="flex-1 px-4 pb-24">{children}</main>
            <TabBar />
          </div>
        </StoreProvider>
      </body>
    </html>
  );
}
