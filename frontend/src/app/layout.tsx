import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Warehouse Digital Twin | Live Dashboard",
  description:
    "Smart Agent-to-Agent, Queue-Aware Digital Twin for Warehouse Logistics — Real-time monitoring dashboard",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
