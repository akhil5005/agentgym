/** A list of episodes, linking into the replay viewer. */

import Link from "next/link";

import { reward, shortDate } from "@/lib/api";
import type { EpisodeSummary } from "@/lib/types";

import { OutcomeBadge, TamperBadge } from "./badges";
import { EmptyState, TableScroll } from "./layout-bits";

export function EpisodeTable({
  episodes,
  showTask = false,
}: {
  episodes: EpisodeSummary[];
  showTask?: boolean;
}) {
  if (episodes.length === 0) {
    return <EmptyState>No episodes recorded for this yet.</EmptyState>;
  }

  return (
    <TableScroll>
      <table className="w-full min-w-[680px] text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="px-4 py-2 font-medium">
              Agent
            </th>
            {showTask && (
              <th scope="col" className="px-4 py-2 font-medium">
                Task
              </th>
            )}
            <th scope="col" className="px-4 py-2 font-medium">
              Outcome
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Reward
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Hidden tests
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Steps
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              Finished
            </th>
            <th scope="col" className="px-4 py-2 font-medium">
              <span className="sr-only">Replay</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {episodes.map((episode) => (
            <tr
              key={episode.id}
              className="border-b border-edge last:border-0 hover:bg-surface-raised"
            >
              <th scope="row" className="px-4 py-2.5 text-left font-normal">
                <span className="font-medium">{episode.agent_name}</span>
                {episode.model && (
                  <span className="mt-0.5 block font-mono text-xs text-muted">
                    {episode.model}
                  </span>
                )}
                {episode.tamper_attempts > 0 && (
                  <span className="mt-1 block">
                    <TamperBadge count={episode.tamper_attempts} />
                  </span>
                )}
              </th>
              {showTask && (
                <td className="px-4 py-2.5">
                  <Link
                    href={`/tasks/${episode.task_id}`}
                    className="font-mono text-xs text-accent hover:underline"
                  >
                    {episode.task_id}
                  </Link>
                </td>
              )}
              <td className="px-4 py-2.5">
                <OutcomeBadge outcome={episode.outcome} />
              </td>
              <td className="tabular px-4 py-2.5 text-right font-medium">
                {reward(episode.reward)}
              </td>
              <td className="tabular px-4 py-2.5 text-right text-muted">
                {episode.tests_passed}/{episode.tests_total}
              </td>
              <td className="tabular px-4 py-2.5 text-right text-muted">
                {episode.steps_used}
              </td>
              <td className="px-4 py-2.5 font-mono text-xs text-muted">
                {shortDate(episode.finished_at)}
              </td>
              <td className="px-4 py-2.5 text-right">
                <Link
                  href={`/episodes/${episode.id}`}
                  className="rounded-md border border-edge px-2 py-1 text-xs text-accent hover:bg-surface"
                >
                  Replay
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
