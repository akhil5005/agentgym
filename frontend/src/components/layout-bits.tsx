/** Page furniture: headings, cards, stat tiles, and the API-down message. */

import Link from "next/link";
import type { ReactNode } from "react";

import { API_HELP, API_IS_REMOTE } from "@/lib/api";
import { Waking } from "@/components/waking";

export function PageHeading({
  title,
  lead,
  children,
}: {
  title: string;
  lead?: string;
  children?: ReactNode;
}) {
  return (
    <header className="mb-8">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
        {title}
      </h1>
      {lead && <p className="mt-2 max-w-2xl text-sm text-muted">{lead}</p>}
      {children}
    </header>
  );
}

export function Card({
  title,
  hint,
  children,
}: {
  title?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-edge bg-surface">
      {title && (
        <div className="border-b border-edge px-4 py-3">
          <h2 className="text-sm font-semibold">{title}</h2>
          {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  hint,
}: {
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="rounded-xl border border-edge bg-surface px-4 py-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">
        {label}
      </div>
      <div className="tabular mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

/**
 * Shown whenever an API call came back null. It names the command to run,
 * because "the backend is not running" is by far the most common cause and the
 * fix is one line.
 */
export function ApiDown({ what }: { what: string }) {
  // Deployed, the overwhelmingly likely cause is "the free host is asleep",
  // which fixes itself in under a minute. Showing a red error for something
  // self-correcting is wrong, and there is no command the reader could run
  // anyway — so hand over to the component that waits and retries.
  if (API_IS_REMOTE) return <Waking what={what} />;

  // Locally, the backend genuinely is not running, and the fix is one line.
  return (
    <div className="rounded-xl border border-failed/40 bg-failed-soft p-4">
      <h2 className="text-sm font-semibold text-failed">
        Could not load {what}
      </h2>
      <p className="mt-2 text-sm text-foreground">
        The dashboard reads everything from the AgentGym API. Start it from the
        repository root:
      </p>
      <pre className="mt-3 overflow-x-auto rounded-lg border border-edge bg-surface p-3 text-xs">
        <code>uvicorn app.main:app --reload --app-dir backend</code>
      </pre>
      <p className="mt-3 text-xs text-muted">{API_HELP.split("\n")[0]}</p>
    </div>
  );
}

/** Shown when a request succeeded but there is simply nothing stored yet. */
export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="px-4 py-10 text-center text-sm text-muted">{children}</div>
  );
}

export function TaskLink({ taskId }: { taskId: string }) {
  return (
    <Link
      href={`/tasks/${taskId}`}
      className="font-mono text-sm text-accent hover:underline"
    >
      {taskId}
    </Link>
  );
}

/**
 * Tables are wider than a phone. Wrapping them in their own scroll container
 * keeps the page body from scrolling sideways, which is the requirement that
 * actually matters at 400px.
 */
export function TableScroll({ children }: { children: ReactNode }) {
  return <div className="overflow-x-auto">{children}</div>;
}
