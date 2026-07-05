import type { Metadata } from "next";
import "./globals.css";
import DashboardLayout from "@/components/DashboardLayout";

export const metadata: Metadata = {
  title: "GameMind Workspace",
  description: "Game design co-pilot for GDD analysis, blueprint generation, and Unity runtime testing.",
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
      <body className="min-h-full flex flex-col bg-[#0a0a0a] text-[#fafafa]">
        <DashboardLayout>{children}</DashboardLayout>
      </body>
    </html>
  );
}
