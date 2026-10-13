import Link from "next/link";

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

export default async function HomePage() {
  // One round trip each, in parallel — the three panels are independent.
  const [stats, leaderboard, matrix] = await Promise.all([
    getStats(),
    getLeaderboard(),
    getMatrix(),
  ]);

  if (!stats || !leaderboard || !matrix) {
    return (
      <>
        <PageHeading title="Overview" />
        <ApiDown what="the results" />
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="AgentGym"
        lead="Each episode hands an agent a small Python project with a bug in it. The agent reads files, writes files and runs the visible tests. When it submits, the engine grades the work against hidden tests the agent never sees — so the reward is the fraction of those that pass, and the cheapest way to score is to actually fix the bug."
      />

      <div className="mb-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatTile label="Tasks" value={stats.tasks} hint="3 easy, 3 medium, 3 hard" />
        <StatTile label="Episodes" value={stats.episodes} hint="attempts recorded" />
        <StatTile label="Agents" value={stats.agents} hint="counting model variants" />
        <StatTile
          label="Reward"
          value="0 – 1"
          hint="hidden tests passed / total"
        />
      </div>

      <div className="space-y-8">
        <Card
          title="Leaderboard"
          hint="The three scripted agents are the reference points that make an LLM score mean something."
        >
          <Leaderboard rows={leaderboard} />
        </Card>

        <Card
          title="Mean reward by task and agent"
          hint="Click a task id to read its brief and browse its episodes."
        >
          <Matrix cells={matrix} />
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
