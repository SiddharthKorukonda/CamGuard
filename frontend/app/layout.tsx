import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CamGuard — Caregiver Protection",
  description: "Agentic fall triage and response system for caregiver cameras",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
