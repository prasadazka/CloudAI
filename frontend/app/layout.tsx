import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { Header } from "@/components/Header";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Cloud Siddhi — Agentic AI Cloud Orchestration",
  description:
    "Cloud Siddhi turns natural-language service requests into compliant, audited AWS deployments. Agentic AI for enterprise SD-WAN and cloud onboarding, by Azkashine.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="flex min-h-screen flex-col bg-zinc-50 font-sans">
        <Header />
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8 lg:py-10">
          {children}
        </main>
        <footer className="border-t border-zinc-200 bg-white py-4">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center justify-between gap-3 px-4 text-xs text-zinc-500 sm:px-6 lg:px-8">
            <span>Cloud Siddhi · an Azkashine product</span>
            <span>Confidential — internal use only</span>
          </div>
        </footer>
      </body>
    </html>
  );
}
