import Link from "next/link";

export const metadata = { title: "Not found" };

export default function NotFound() {
  return (
    <div className="mx-auto max-w-md py-12 text-center">
      <h1 className="text-2xl font-semibold">Not found</h1>
      <p className="mt-3 text-sm text-muted">
        That task or episode is not in the database. It may not have been
        uploaded yet — results are uploaded from the machine that runs the
        episodes.
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3 text-sm">
        <Link
          href="/"
          className="rounded-md bg-accent px-3 py-1.5 text-accent-contrast hover:opacity-90"
        >
          Overview
        </Link>
        <Link
          href="/tasks"
          className="rounded-md border border-edge px-3 py-1.5 hover:bg-surface"
        >
          All tasks
        </Link>
      </div>
    </div>
  );
}
