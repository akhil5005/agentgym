import Link from "next/link";

import { DifficultyBadge } from "@/components/badges";
import {
  ApiDown,
  Card,
  EmptyState,
  PageHeading,
  TableScroll,
} from "@/components/layout-bits";
import { getTasks, percent, reward } from "@/lib/api";

/**
 * A live results dashboard: every page reads fresh data on each request, so the
 * route blocks on the API instead of being prerendered into a static shell.
 * Without this, Next's Cache Components check fails the build.
 */
export const instant = false

export const metadata = { title: "Tasks" };

export default async function TasksPage() {
  const tasks = await getTasks();

  if (!tasks) {
    return (
      <>
        <PageHeading title="Tasks" />
        <ApiDown what="the task list" />
      </>
    );
  }

  return (
    <>
      <PageHeading
        title="Tasks"
        lead="Nine buggy Python projects. Each has visible tests the agent can run, hidden tests it is graded on, and a reference fix used to prove the task is solvable."
      />

      <Card>
        {tasks.length === 0 ? (
          <EmptyState>
            No tasks yet. Run{" "}
            <code className="font-mono text-xs">
              python -m agentgym.runner sync-tasks --api ... --key ...
            </code>
            .
          </EmptyState>
        ) : (
          <TableScroll>
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-edge text-left text-xs uppercase tracking-wide text-muted">
                  <th scope="col" className="px-4 py-2 font-medium">
                    Task
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Difficulty
                  </th>
                  <th scope="col" className="px-4 py-2 font-medium">
                    Category
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
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr
                    key={task.id}
                    className="border-b border-edge last:border-0 hover:bg-surface-raised"
                  >
                    <th scope="row" className="px-4 py-2.5 text-left font-normal">
                      <Link
                        href={`/tasks/${task.id}`}
                        className="text-accent hover:underline"
                      >
                        <span className="font-mono text-xs">{task.id}</span>
                        <span className="mt-0.5 block font-sans text-sm text-foreground">
                          {task.title}
                        </span>
                      </Link>
                    </th>
                    <td className="px-4 py-2.5">
                      <DifficultyBadge difficulty={task.difficulty} />
                    </td>
                    <td className="px-4 py-2.5 text-muted">{task.category}</td>
                    <td className="tabular px-4 py-2.5 text-right">
                      {task.episodes}
                    </td>
                    <td className="tabular px-4 py-2.5 text-right">
                      {task.episodes ? percent(task.solve_rate) : "—"}
                    </td>
                    <td className="tabular px-4 py-2.5 text-right font-medium">
                      {task.episodes ? reward(task.mean_reward) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        )}
      </Card>
    </>
  );
}
