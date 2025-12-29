import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Mera AI - Unified AI Assistant",
  description: "AI assistant with Research → Plan → Implement workflow",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
