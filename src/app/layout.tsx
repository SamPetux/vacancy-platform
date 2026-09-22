import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Vacancy Platform",
  description: "Browse and post job vacancies.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="sticky top-0 z-10 border-b border-border bg-card/80 backdrop-blur">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="flex items-center gap-2 font-semibold">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-primary text-sm font-bold text-white">
                VP
              </span>
              <span>Vacancy Platform</span>
            </Link>
            <nav className="flex items-center gap-2 text-sm">
              <Link
                href="/"
                className="rounded-md px-3 py-1.5 text-muted transition hover:bg-background hover:text-foreground"
              >
                Browse
              </Link>
              <Link
                href="/post"
                className="rounded-md bg-primary px-3 py-1.5 font-medium text-white transition hover:opacity-90"
              >
                Post a job
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border py-6 text-center text-sm text-muted">
          Vacancy Platform — a starter project.
        </footer>
      </body>
    </html>
  );
}
