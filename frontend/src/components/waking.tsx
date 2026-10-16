"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

/**
 * Shown when the API did not answer, which on a free host almost always means
 * "asleep", not "broken".
 *
 * A free Render service spins down after 15 minutes idle and takes 30-60s to
 * wake (measured: 42s). The old behaviour was a red error card telling the
 * reader to run uvicorn — a dead end for anyone who is not the author.
 *
 * This retries on its own instead. `router.refresh()` re-runs the server
 * component, so the moment the API is up the real dashboard replaces this with
 * no interaction. Giving up is also handled: after enough attempts it stops
 * and offers a button, rather than reloading forever.
 */

const RETRY_EVERY_S = 8;
const MAX_ATTEMPTS = 9; // ~72s of patience, comfortably past a cold start

export function Waking({ what }: { what: string }) {
  const router = useRouter();
  const [attempt, setAttempt] = useState(1);
  const [seconds, setSeconds] = useState(RETRY_EVERY_S);
  const givenUp = attempt > MAX_ATTEMPTS;

  useEffect(() => {
    if (givenUp) return;
    const tick = setInterval(() => {
      setSeconds((s) => {
        if (s > 1) return s - 1;
        // Re-run the server component; if the API is awake the page fills in.
        router.refresh();
        setAttempt((a) => a + 1);
        return RETRY_EVERY_S;
      });
    }, 1000);
    return () => clearInterval(tick);
  }, [givenUp, router]);

  const elapsed = (attempt - 1) * RETRY_EVERY_S;

  return (
    <div
      className="rounded-xl border border-edge bg-surface p-5"
      role="status"
      aria-live="polite"
    >
      <div className="flex items-center gap-3">
        {!givenUp && (
          <span
            aria-hidden
            className="h-4 w-4 shrink-0 animate-spin rounded-full border-2 border-edge border-t-accent motion-reduce:animate-none"
          />
        )}
        <h2 className="text-sm font-semibold text-foreground">
          {givenUp ? `Still waiting on ${what}` : `Waking the server…`}
        </h2>
      </div>

      <p className="mt-2 text-sm text-muted">
        {givenUp ? (
          <>
            The API has not answered in {elapsed} seconds, which is longer than a
            normal wake-up. It may be mid-deploy.
          </>
        ) : (
          <>
            This dashboard runs on a free host that sleeps when nobody is using
            it. The first visit wakes it, which takes up to a minute — {what}{" "}
            will appear here automatically.
          </>
        )}
      </p>

      {!givenUp ? (
        <p className="mt-3 text-xs tabular-nums text-muted">
          Checking again in {seconds}s · attempt {attempt} of {MAX_ATTEMPTS}
        </p>
      ) : (
        <button
          type="button"
          onClick={() => {
            setAttempt(1);
            setSeconds(RETRY_EVERY_S);
            router.refresh();
          }}
          className="mt-3 rounded-lg border border-edge px-3 py-1.5 text-sm text-foreground hover:bg-raised focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
        >
          Try again
        </button>
      )}
    </div>
  );
}
