import type { Metadata } from "next";
import { ThemeToggle } from "@/components/ThemeToggle";
import { AuthProvider } from "@/context/AuthContext";
import { ThemeProvider } from "@/context/ThemeContext";
import "./globals.css";
import { Geist } from "next/font/google";
import { cn } from "@/lib/utils";

const geist = Geist({subsets:['latin'],variable:'--font-sans'});

export const metadata: Metadata = {
  title: "TVS NADI",
  description: "Adaptive Credit Path Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning className={cn("font-sans", geist.variable)}>
      <body>
        <ThemeProvider><AuthProvider>{children}</AuthProvider><ThemeToggle /></ThemeProvider>
      </body>
    </html>
  );
}
