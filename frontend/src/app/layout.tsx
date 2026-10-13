import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  // The "%s" is filled in by each page's own title.
  title: { default: "AgentGym", template: "%s · AgentGym" },
  description:
    "A reinforcement-learning environment for AI coding agents: nine buggy " +
    "Python projects, hidden-test grading, and anti-reward-hacking checks.",
};

const NAV = [
  { href: "/", label: "Overview" },
  { href: "/tasks", label: "Tasks" },
  { href: "/about", label: "About" },
];

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent focus:px-3 focus:py-2 focus:text-sm focus:text-accent-contrast"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-40 border-b border-edge bg-surface/90 backdrop-blur">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              AgentGym
            </Link>
            <nav aria-label="Main" className="flex gap-1 text-sm">
              {NAV.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className="rounded-md px-2.5 py-1 text-muted hover:bg-surface-raised hover:text-foreground"
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
        </header>

        <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
          {children}
        </main>

        <footer className="border-t border-edge px-4 py-6 text-center text-xs text-muted">
          Agent code runs only on the machine that plays the episodes. This
          dashboard just stores and shows the results.
        </footer>
      </body>
    </html>
  );
}
