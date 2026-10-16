import Link from "next/link";
import { Suspense } from "react";

import { Leaderboard } from "@/components/leaderboard";
import {
  ApiDown,
  Card,
  PageHeading,
  StatTile,
} from "@/components/layout-bits";
import { Matrix } from "@/components/matrix";
import { getLeaderboard, getMatrix, getStats } from "@/lib/api";

/**
 * A live results dashboard: every page reads fresh data on each request, so the
 * route blocks on the API instead of being prerendered into a static shell.
 * Without this, Next's Cache Components check fails the build.
 */
export const instant = false

export const metadata = { title: "Overview" };

const LEAD =
  "Each episode hands an agent a small Python project with a bug in it. The agent reads files, writes files and runs the visible tests. When it submits, the engine grades the work against hidden tests the agent never sees — so the reward is the fraction of those that pass, and the cheapest way to score is to actually fix the bug.";

/**
 * The page renders in two parts on purpose.
 *
 * The heading and the explanation below need no API call, so they are returned
 * immediately. Everything that does need data lives inside <Suspense>, which
 * streams in when it is ready. On a free host whose API sleeps and takes up to
 * a minute to wake, that is the difference between a blank screen and a page
 * that is already readable while the numbers are still on their way.
 */
export default function HomePage() {
  return (
    <>
      <PageHeading title="AgentGym" lead={LEAD} />

      <Suspense fallback={<StatTilesSkeleton />}>
        <StatTiles />
      </Suspense>

      <div className="space-y-8">
        <Card
          title="Leaderboard"
          hint="The three scripted agents are the reference points that make an LLM score mean something."
        >
          <Suspense fallback={<PanelSkeleton rows={4} />}>
            <LeaderboardPanel />
          </Suspense>
        </Card>

        <Card
          title="Mean reward by task and agent"
          hint="Click a task id to read its brief and browse its episodes."
        >
          <Suspense fallback={<PanelSkeleton rows={9} />}>
            <MatrixPanel />
          </Suspense>
        </Card>
      </div>

      <p className="mt-8 text-sm text-muted">
        New here?{" "}
        <Link href="/about" className="text-accent hover:underline">
          What all of this means
        </Link>
        .
      </p>
    </>
  );
}

// --- the three data-dependent panels, each awaiting only its own call -------
//
// Separate components rather than one Promise.all: a slow matrix query should
// not hold up the leaderboard, and each can fail — and retry — on its own.

async function StatTiles() {
  const stats = await getStats();
  if (!stats) return <ApiDown what="the totals" />;

  return (
    <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
      <StatTile label="Tasks" value={stats.tasks} hint="3 easy, 3 medium, 3 hard" />
      <StatTile label="Episodes" value={stats.episodes} hint="attempts recorded" />
      <StatTile label="Agents" value={stats.agents} hint="counting model variants" />
      <StatTile label="Reward" value="0 – 1" hint="hidden tests passed / total" />
    </div>
  );
}

async function LeaderboardPanel() {
  const rows = await getLeaderboard();
  if (!rows) return <ApiDown what="the leaderboard" />;
  return <Leaderboard rows={rows} />;
}

async function MatrixPanel() {
  const cells = await getMatrix();
  if (!cells) return <ApiDown what="the matrix" />;
  return <Matrix cells={cells} />;
}

// --- placeholders shown while the above are in flight -----------------------

function StatTilesSkeleton() {
  return (
    <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4" aria-hidden>
      {Array.from({ length: 4 }, (_, i) => (
        <div
          key={i}
          className="h-[88px] animate-pulse rounded-xl border border-edge bg-surface motion-reduce:animate-none"
        />
      ))}
    </div>
  );
}

function PanelSkeleton({ rows }: { rows: number }) {
  return (
    <div className="space-y-2 p-4" aria-hidden>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="h-8 animate-pulse rounded-lg bg-surface-raised motion-reduce:animate-none"
        />
      ))}
    </div>
  );
}
