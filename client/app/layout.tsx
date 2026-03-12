import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/store";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthInitializer } from "@/components/AuthInitializer";
import { ToastProvider } from "@/components/ToastProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "PolyGot",
  description: "Multilingual communication platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full overflow-hidden">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased h-full overflow-hidden`}
      >
        <ErrorBoundary>
          <StoreProvider>
            <ToastProvider />
            <AuthInitializer>{children}</AuthInitializer>
          </StoreProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
