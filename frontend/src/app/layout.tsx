import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import ClassificationBanner from "@/components/shared/ClassificationBanner";
import Sidebar from "@/components/shared/Sidebar";

export const metadata: Metadata = {
  title: "Sovereign AI Hub",
  description: "Air-gapped, locally-run AI platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[var(--color-bg)] text-[var(--color-text)] min-h-screen">
        <ClassificationBanner />
        <div className="flex h-screen" style={{ paddingTop: "22px", paddingBottom: "22px" }}>
          <Suspense fallback={<aside className="w-12 bg-[var(--color-surface)] shrink-0" />}>
            <Sidebar />
          </Suspense>
          <main className="flex-1 overflow-hidden">{children}</main>
        </div>
      </body>
    </html>
  );
}
