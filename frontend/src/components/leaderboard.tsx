/** The leaderboard table: one row per agent, best mean reward first. */

import { percent, reward } from "@/lib/api";
import type { LeaderboardRow } from "@/lib/types";

import { EmptyState, TableScroll } from "./layout-bits";

/**
 * Scripted agents are reference points, not competitors — say which is which,
 * so a reader can tell the baselines apart from the model being measured.
 */
const ROLE: Record<string, string> = {
  oracle: "ceiling — applies the reference fix, must score 1.000",
  noop: "floor — submits immediately, scores what the bug already passes",
  tamper: "control — only tries to cheat, must never beat noop",
  gemini: "the model under test — reads, edits and runs the tests itself",
  anthropic: "alternative LLM, kept for comparison; not the default",
};

export function Leaderboard({ rows }: { rows: LeaderboardRow[] }) {
  if (rows.length === 0) {
    return (
      <EmptyState>
        No episodes yet. Run{" "}
        <code className="font-mono text-xs">
          python -m agentgym.runner run --agent oracle --tasks all --out
          runs/oracle.jsonl
        </code>{" "}
        and upload it.
      </EmptyState>
    );
  }

  return (
    <TableScroll>
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-edge text-left text-xs uppercase tracking-wide text-muted">
            <th scope="col" className="px-4 py-2 font-medium">
              Agent
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Episodes
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Solve rate
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Mean reward
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Mean steps
            </th>
            <th scope="col" className="px-4 py-2 text-right font-medium">
              Tamper rate
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.label}
              className="border-b border-edge last:border-0 hover:bg-surface-raised"
            >
              <th scope="row" className="px-4 py-2.5 text-left font-normal">
                <span className="font-medium">{row.label}</span>
                {ROLE[row.agent_name] && (
                  <span className="mt-0.5 block text-xs text-muted">
                    {ROLE[row.agent_name]}
                  </span>
                )}
              </th>
              <td className="tabular px-4 py-2.5 text-right">{row.episodes}</td>
              <td className="tabular px-4 py-2.5 text-right">
                {percent(row.solve_rate)}
              </td>
              <td className="tabular px-4 py-2.5 text-right font-medium">
                {reward(row.mean_reward)}
              </td>
              <td className="tabular px-4 py-2.5 text-right text-muted">
                {row.mean_steps.toFixed(1)}
              </td>
              <td className="tabular px-4 py-2.5 text-right">
                <span className={row.tamper_rate > 0 ? "text-failed" : "text-muted"}>
                  {percent(row.tamper_rate)}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
