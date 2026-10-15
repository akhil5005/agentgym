import Link from "next/link";
import { notFound } from "next/navigation";

import { OutcomeBadge, TamperBadge } from "@/components/badges";
import { ApiDown, PageHeading, StatTile } from "@/components/layout-bits";
import { ReplayViewer } from "@/components/replay-viewer";
import { getEpisode, getEpisodes, reward, shortDate } from "@/lib/api";

/**
 * A live results dashboard: every page reads fresh data on each request, so the
 * route blocks on the API instead of being prerendered into a static shell.
 * Without this, Next's Cache Components check fails the build.
 *
 * Known trade-off: this route is partially prerendered, so the 200 response
 * headers are already flushed (`x-nextjs-postponed: 1`) by the time the data
 * arrives and `notFound()` runs below. A missing id therefore renders the
 * not-found page with a 200 rather than a 404 — a "soft 404". Opting out of
 * PPR would fix the status, at the cost of showing nothing at all until the API
 * answers, which on a free tier waking from sleep is 30-60 seconds. For a
 * results dashboard with no SEO requirement, the instant shell is worth more
 * than the correct status code. Next's own /no-such-page 404 is unaffected.
 */
export const instant = false

type Props = PageProps<"/episodes/[id]">;

export async function generateMetadata({ params }: Props) {
  const { id } = await params;
  const episode = await getEpisode(id);
  return {
    title: episode ? `${episode.agent_name} on ${episode.task_id}` : "Episode",
  };
}

export default async function EpisodePage({ params }: Props) {
  const { id } = await params;
  const episode = await getEpisode(id);

  if (!episode) {
    // Tell "backend down" apart from "no such episode" before choosing a page.
    const reachable = await getEpisodes({ limit: 1 });
    if (reachable === null) {
      return (
        <>
          <PageHeading title="Episode" />
          <ApiDown what="this episode" />
        </>
      );
    }
    notFound();
  }

  return (
    <>
      <PageHeading title={`${episode.agent_name} on ${episode.task_id}`}>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <OutcomeBadge outcome={episode.outcome} />
          {episode.model && (
            <code className="rounded-md border border-edge bg-surface px-2 py-0.5 font-mono text-xs">
              {episode.model}
            </code>
          )}
          {episode.tamper_attempts > 0 && (
            <TamperBadge count={episode.tamper_attempts} />
          )}
          <Link
            href={`/tasks/${episode.task_id}`}
            className="text-accent hover:underline"
          >
            View task
          </Link>
        </div>
      </PageHeading>

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile
          label="Reward"
          value={reward(episode.reward)}
          hint="hidden tests passed / total"
        />
        <StatTile
          label="Hidden tests"
          value={`${episode.tests_passed}/${episode.tests_total}`}
        />
        <StatTile label="Steps used" value={episode.steps_used} />
        <StatTile
          label="Trial"
          value={episode.trial}
          // Say what the timestamp is. Bare under "Trial" it reads as though
          // the date somehow belongs to the trial number.
          hint={`finished ${shortDate(episode.finished_at)}`}
        />
      </div>

      <h2 className="mb-3 text-lg font-semibold">Replay</h2>
      <p className="mb-4 max-w-2xl text-sm text-muted">
        Every action the agent took, in order, with what the environment replied.
        Reward is zero on every step except the last, where the hidden tests are
        run.
      </p>

      <ReplayViewer episode={episode} />
    </>
  );
}
