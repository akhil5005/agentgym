/**
 * Small labels used across every page.
 *
 * Each badge pairs a colour with the word itself, never colour alone — so the
 * dashboard still reads correctly in greyscale or with colour-blindness.
 */

import type { Difficulty } from "@/lib/types";

const BASE =
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap";

const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  easy: "border-solved/40 bg-solved-soft text-solved",
  medium: "border-partial/40 bg-partial-soft text-partial",
  hard: "border-failed/40 bg-failed-soft text-failed",
};

export function DifficultyBadge({ difficulty }: { difficulty: string }) {
  const style =
    DIFFICULTY_STYLE[difficulty as Difficulty] ??
    "border-edge bg-neutral-soft text-muted";
  return <span className={`${BASE} ${style}`}>{difficulty}</span>;
}

/**
 * Outcome colours group by meaning rather than giving each its own hue:
 * green solved it, amber got part way, red broke, grey changed nothing.
 */
const OUTCOME_STYLE: Record<string, string> = {
  solved: "border-solved/40 bg-solved-soft text-solved",
  partial: "border-partial/40 bg-partial-soft text-partial",
  out_of_steps: "border-partial/40 bg-partial-soft text-partial",
  wrong_fix: "border-failed/40 bg-failed-soft text-failed",
  error: "border-failed/40 bg-failed-soft text-failed",
  timeout: "border-failed/40 bg-failed-soft text-failed",
  no_change: "border-edge-strong bg-neutral-soft text-muted",
};

/** Plain-English explanation, shown as a tooltip on the badge. */
const OUTCOME_HELP: Record<string, string> = {
  solved: "Every hidden test passed.",
  partial: "Some hidden tests passed; the fix was not general.",
  wrong_fix: "Files were changed but no hidden test passed.",
  no_change: "The agent never successfully wrote a file.",
  out_of_steps: "The step limit was reached before submitting.",
  timeout: "The tests were killed for running too long.",
  error: "The hidden tests could not run, so nothing was scored.",
};

export function OutcomeBadge({ outcome }: { outcome: string }) {
  const style =
    OUTCOME_STYLE[outcome] ?? "border-edge bg-neutral-soft text-muted";
  return (
    <span className={`${BASE} ${style}`} title={OUTCOME_HELP[outcome] ?? outcome}>
      {outcome.replace(/_/g, " ")}
    </span>
  );
}

/** Shown on any step where the guard refused a write. */
export function TamperBadge({ count }: { count?: number }) {
  return (
    <span
      className={`${BASE} border-failed/50 bg-failed-soft text-failed`}
      title="The anti-reward-hacking guard refused this write. It still cost the agent a step."
    >
      tamper blocked{count !== undefined && count > 1 ? ` x${count}` : ""}
    </span>
  );
}
