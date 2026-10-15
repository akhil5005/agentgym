/**
 * Every call to the backend lives here.
 *
 * Three deliberate choices:
 *
 * 1. `cache: "no-store"` on every request. This is a results dashboard — a
 *    cached leaderboard that does not change after you upload a run is worse
 *    than a slightly slower one.
 * 2. A fetch failure returns `null` rather than throwing. A page can then
 *    render a "start the backend like this" message instead of a crash, which
 *    is the single most likely thing to go wrong when someone clones this.
 * 3. Transport failures are retried. A free-tier host sleeps after ~15 minutes
 *    idle and takes 20-30 seconds to wake — measured at 22s on Render, against
 *    0.35s warm. Without a retry the first visit after a quiet period always
 *    shows the error card, which is exactly when someone is being shown the
 *    site. A real 4xx is a genuine answer and is never retried.
 */

import type {
  EpisodeDetail,
  EpisodeSummary,
  LeaderboardRow,
  MatrixCell,
  Stats,
  Task,
} from "./types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** True when the API is a remote service rather than one you start yourself. */
export const API_IS_REMOTE = /^https?:\/\/(?!localhost|127\.0\.0\.1|\[::1\])/i
  .test(API_URL);

/** What to tell the reader when the backend cannot be reached. */
export const API_HELP = API_IS_REMOTE
  ? `Could not reach the API at ${API_URL}. A free-tier service sleeps when idle and can take about a minute to wake — reload in a moment.`
  : `Could not reach the API at ${API_URL}. Start it with:
uvicorn app.main:app --reload --app-dir backend`;

/** Per-attempt budget. Longer than a warm request by two orders of magnitude. */
const ATTEMPT_TIMEOUT_MS = 15_000;
const ATTEMPTS = 3;
const RETRY_DELAY_MS = 2_000;

const wait = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

async function getJson<T>(path: string): Promise<T | null> {
  for (let attempt = 1; attempt <= ATTEMPTS; attempt += 1) {
    const isLast = attempt === ATTEMPTS;
    try {
      const response = await fetch(`${API_URL}${path}`, {
        cache: "no-store",
        signal: AbortSignal.timeout(ATTEMPT_TIMEOUT_MS),
      });

      // A 404 is a real answer ("no such episode"), not a transport failure, so
      // it comes back as null too and the caller shows its not-found page.
      // A 5xx can mean the host is still booting, so that one is worth retrying.
      if (!response.ok) {
        if (response.status >= 500 && !isLast) {
          await wait(RETRY_DELAY_MS);
          continue;
        }
        return null;
      }

      return (await response.json()) as T;
    } catch {
      // Timed out, DNS not resolving yet, connection refused — all the shapes
      // a sleeping service takes. Worth another go.
      if (isLast) return null;
      await wait(RETRY_DELAY_MS);
    }
  }
  return null;
}

export function getStats(): Promise<Stats | null> {
  return getJson<Stats>("/api/stats");
}

export function getLeaderboard(): Promise<LeaderboardRow[] | null> {
  return getJson<LeaderboardRow[]>("/api/leaderboard");
}

export function getMatrix(): Promise<MatrixCell[] | null> {
  return getJson<MatrixCell[]>("/api/matrix");
}

export function getTasks(): Promise<Task[] | null> {
  return getJson<Task[]>("/api/tasks");
}

export function getTask(taskId: string): Promise<Task | null> {
  return getJson<Task>(`/api/tasks/${encodeURIComponent(taskId)}`);
}

export function getEpisode(episodeId: string): Promise<EpisodeDetail | null> {
  return getJson<EpisodeDetail>(`/api/episodes/${encodeURIComponent(episodeId)}`);
}

export interface EpisodeFilters {
  taskId?: string;
  agent?: string;
  outcome?: string;
  limit?: number;
  offset?: number;
}

export function getEpisodes(
  filters: EpisodeFilters = {},
): Promise<EpisodeSummary[] | null> {
  const query = new URLSearchParams();
  if (filters.taskId) query.set("task_id", filters.taskId);
  if (filters.agent) query.set("agent", filters.agent);
  if (filters.outcome) query.set("outcome", filters.outcome);
  if (filters.limit !== undefined) query.set("limit", String(filters.limit));
  if (filters.offset !== undefined) query.set("offset", String(filters.offset));

  const suffix = query.toString();
  return getJson<EpisodeSummary[]>(
    `/api/episodes${suffix ? `?${suffix}` : ""}`,
  );
}

// --- small formatting helpers, shared by every page ------------------------

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function reward(value: number): string {
  return value.toFixed(3);
}

export function shortDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  // A fixed locale, so the server-rendered string and the browser's agree.
  return date.toISOString().replace("T", " ").slice(0, 19) + "Z";
}
