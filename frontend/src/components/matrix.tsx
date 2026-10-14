/**
 * The task-by-agent results matrix.
 *
 * A sequential single-hue heatmap: mean reward runs from 0 to 1, so one colour
 * getting stronger is the honest encoding (a red-to-green diverging scale would
 * imply a meaningful midpoint, and there isn't one). The number is printed in
 * every cell, so colour is never the only signal.
 */

import { percent, reward } from "@/lib/api";
import type { MatrixCell } from "@/lib/types";

import { EmptyState, TableScroll, TaskLink } from "./layout-bits";

/** Background tint for a mean reward. Buckets, not a gradient, so the steps
 *  stay distinguishable and every tint keeps readable text contrast. */
function tint(value: number): string {
  if (value >= 1) return "bg-solved/55 font-semibold";
  if (value >= 0.7) return "bg-solved/35";
  if (value >= 0.35) return "bg-solved/20";
  if (value > 0) return "bg-solved/10";
  return "bg-neutral-soft";
}

export function Matrix({ cells }: { cells: MatrixCell[] }) {
  if (cells.length === 0) {
    return <EmptyState>No episodes yet, so there is nothing to compare.</EmptyState>;
  }

  // One column per agent. Keep the name and model separate: joined into one
  // string, a long model id ("gemini-3.5-flash-lite") stretches its column to
  // several times the width of the others and strands the numbers.
  const columns = [
    ...new Map(
      cells.map((cell) => [
        cell.label,
        { label: cell.label, name: cell.agent_name, model: cell.model },
      ]),
    ).values(),
  ].sort((a, b) => a.label.localeCompare(b.label));

  const taskIds = [...new Set(cells.map((cell) => cell.task_id))].sort();

  const byKey = new Map(cells.map((cell) => [`${cell.task_id}|${cell.label}`, cell]));

  return (
    <>
      <TableScroll>
        <table className="w-full min-w-[520px] border-collapse text-sm">
          <caption className="sr-only">
            Mean reward for each task and agent. Higher is better; 1.000 means
            every hidden test passed.
          </caption>
          <thead>
            <tr className="text-xs uppercase tracking-wide text-muted">
              <th scope="col" className="px-4 py-2 text-left font-medium">
                Task
              </th>
              {columns.map((column) => (
                <th
                  key={column.label}
                  scope="col"
                  // A fixed width per agent column, so every agent gets the
                  // same space whatever its model is called.
                  className="w-24 px-3 py-2 text-right align-bottom font-medium"
                >
                  <span className="block">{column.name}</span>
                  {column.model && (
                    <span className="mt-0.5 block font-mono text-[0.625rem] leading-tight font-normal normal-case break-all opacity-80">
                      {column.model}
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {taskIds.map((taskId) => (
              <tr key={taskId} className="border-t border-edge">
                <th scope="row" className="px-4 py-2 text-left font-normal">
                  <TaskLink taskId={taskId} />
                </th>
                {columns.map((column) => {
                  const cell = byKey.get(`${taskId}|${column.label}`);
                  if (!cell) {
                    return (
                      <td
                        key={column.label}
                        className="px-3 py-2 text-right text-muted"
                        title="Not attempted"
                      >
                        {/* An em dash, not 0.000: "never tried" and "scored
                            zero" are different facts. */}
                        &mdash;
                      </td>
                    );
                  }
                  return (
                    <td
                      key={column.label}
                      className={`tabular px-3 py-2 text-right ${tint(cell.mean_reward)}`}
                      title={`${column.label} on ${taskId}: mean reward ${reward(
                        cell.mean_reward,
                      )}, solved ${percent(cell.solve_rate)} of ${cell.n} episode(s)`}
                    >
                      {reward(cell.mean_reward)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-edge px-4 py-3 text-xs text-muted">
        <span>Mean reward:</span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-5 rounded border border-edge bg-neutral-soft" />
          0.000
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-5 rounded border border-edge bg-solved/20" />
          mid
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-3 w-5 rounded border border-edge bg-solved/55" />
          1.000 (solved)
        </span>
        <span>&mdash; = not attempted</span>
      </div>
    </>
  );
}
