import type { Metadata } from "next";
import "./globals.css";
import DashboardLayout from "@/components/DashboardLayout";

export const metadata: Metadata = {
  title: "GameMind Workspace",
  description: "Local-first AI game builder for GDD analysis, grounded blueprints, and runtime integration.",
  icons: {
    icon: "/brand/gamemind-icon.svg",
    apple: "/brand/gamemind-icon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full flex flex-col bg-[var(--background)] text-[var(--foreground)]">
        <DashboardLayout>{children}</DashboardLayout>
      </body>
    </html>
  );
}
