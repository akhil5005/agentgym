"use client";

/**
 * The episode replay viewer.
 *
 * Left: every step in order. Right: the selected step in full. Previous/Next
 * buttons, left/right arrow keys, and a timeline bar coloured by action type.
 *
 * This is a client component because it holds the selected-step state; the
 * episode itself is fetched on the server and passed in, so there is no
 * loading spinner and no API call from the browser.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { EpisodeDetail, Step } from "@/lib/types";

import { TamperBadge } from "./badges";

/** One colour per action type, used by both the list icons and the timeline. */
const ACTION_STYLE: Record<string, { bar: string; chip: string; glyph: string }> = {
  list_files: {
    bar: "bg-neutral",
    chip: "border-edge-strong bg-neutral-soft text-muted",
    glyph: "≡",
  },
  read_file: {
    bar: "bg-accent",
    chip: "border-accent/40 bg-accent/10 text-accent",
    glyph: "◇",
  },
  write_file: {
    bar: "bg-partial",
    chip: "border-partial/40 bg-partial-soft text-partial",
    glyph: "✎",
  },
  run_tests: {
    bar: "bg-solved",
    chip: "border-solved/40 bg-solved-soft text-solved",
    glyph: "▶",
  },
  submit: {
    bar: "bg-foreground",
    chip: "border-edge-strong bg-surface-raised text-foreground",
    glyph: "✔",
  },
  invalid: {
    bar: "bg-failed",
    chip: "border-failed/40 bg-failed-soft text-failed",
    glyph: "!",
  },
};

function styleFor(step: Step) {
  // A blocked write is the most important thing on the timeline, so it
  // overrides the action's own colour.
  if (step.tamper_blocked) {
    return {
      bar: "bg-failed",
      chip: "border-failed/50 bg-failed-soft text-failed",
      glyph: "⛔",
    };
  }
  return ACTION_STYLE[step.action_type] ?? ACTION_STYLE.invalid;
}

/** A write's content, shown as code with line numbers. */
function CodeBlock({ content }: { content: string }) {
  const lines = content.split("\n");
  return (
    <div className="overflow-x-auto rounded-lg border border-edge bg-surface-raised">
      <table className="w-full border-collapse font-mono text-xs">
        <tbody>
          {lines.map((line, index) => (
            <tr key={index}>
              <td
                className="tabular w-10 select-none border-r border-edge px-2 py-0.5 text-right align-top text-muted"
                aria-hidden="true"
              >
                {index + 1}
              </td>
              <td className="whitespace-pre px-3 py-0.5">{line || " "}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReplayViewer({ episode }: { episode: EpisodeDetail }) {
  const [selected, setSelected] = useState(0);
  const steps = episode.steps;
  const total = steps.length;
  const listRef = useRef<HTMLOListElement>(null);
  // Set when the selection changed via the keyboard, so focus can follow it.
  // Without this, arrow keys move the highlight while focus stays where it was,
  // leaving two competing "current" markers on screen — and a screen reader
  // never hears that anything changed.
  const moveFocusRef = useRef(false);

  const go = useCallback(
    (next: number, viaKeyboard = false) => {
      setSelected((current) => {
        const target = Math.min(Math.max(next, 0), Math.max(total - 1, 0));
        if (target === current) return current;
        moveFocusRef.current = viaKeyboard;
        return target;
      });
    },
    [total],
  );

  // Left/right arrows step through the trajectory. Ignored while the user is
  // typing in a field, so this never fights a form.
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      if (event.key === "ArrowLeft") {
        event.preventDefault();
        go(selected - 1, true);
      } else if (event.key === "ArrowRight") {
        event.preventDefault();
        go(selected + 1, true);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [go, selected]);

  // Keep the selected row visible, and let focus follow a keyboard move so the
  // highlight and the focus ring never point at different steps.
  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const row = list.querySelectorAll("li")[selected];
    row?.scrollIntoView({ block: "nearest" });
    if (moveFocusRef.current) {
      moveFocusRef.current = false;
      row?.querySelector("button")?.focus();
    }
  }, [selected]);

  if (total === 0) {
    return (
      <p className="rounded-xl border border-edge bg-surface p-6 text-sm text-muted">
        This episode has no recorded steps.
      </p>
    );
  }

  const step = steps[selected];
  const style = styleFor(step);

  return (
    <div className="space-y-4">
      {/* Timeline: the whole episode at a glance, one segment per step. */}
      <div>
        <div
          className="flex gap-0.5"
          role="group"
          aria-label="Episode timeline"
        >
          {steps.map((item, index) => (
            <button
              key={item.index}
              type="button"
              onClick={() => go(index)}
              aria-label={`Step ${index + 1}: ${item.action_type}`}
              aria-current={index === selected ? "true" : undefined}
              title={`Step ${index + 1}: ${item.action_type}`}
              className={`h-6 flex-1 rounded-sm transition-opacity ${
                styleFor(item).bar
              } ${index === selected ? "ring-2 ring-accent ring-offset-1 ring-offset-background" : "opacity-60 hover:opacity-100"}`}
            />
          ))}
        </div>
        <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted">
          {Object.entries(ACTION_STYLE).map(([name, item]) => (
            <span key={name} className="flex items-center gap-1.5">
              <span className={`h-2.5 w-2.5 rounded-sm ${item.bar}`} />
              {name}
            </span>
          ))}
          <span className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-sm bg-failed" />
            tamper blocked
          </span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[18rem_1fr]">
        {/* Step list */}
        <ol
          ref={listRef}
          className="max-h-[32rem] overflow-y-auto rounded-xl border border-edge bg-surface"
        >
          {steps.map((item, index) => {
            const itemStyle = styleFor(item);
            return (
              <li key={item.index}>
                <button
                  type="button"
                  onClick={() => go(index)}
                  aria-current={index === selected ? "step" : undefined}
                  className={`flex w-full items-start gap-2 border-b border-edge px-3 py-2 text-left text-sm last:border-0 ${
                    index === selected
                      ? "bg-accent/10"
                      : "hover:bg-surface-raised"
                  }`}
                >
                  <span
                    aria-hidden="true"
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border text-[0.7rem] ${itemStyle.chip}`}
                  >
                    {itemStyle.glyph}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="flex items-baseline gap-2">
                      <span className="tabular text-xs text-muted">
                        {index + 1}
                      </span>
                      <span className="truncate font-medium">
                        {item.action_type}
                      </span>
                    </span>
                    {item.action.path && (
                      <span className="mt-0.5 block truncate font-mono text-xs text-muted">
                        {item.action.path}
                      </span>
                    )}
                  </span>
                  {item.reward > 0 && (
                    <span className="tabular shrink-0 text-xs font-medium text-solved">
                      +{item.reward.toFixed(2)}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ol>

        {/* Selected step */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-edge bg-surface px-4 py-3">
            <button
              type="button"
              onClick={() => go(selected - 1)}
              disabled={selected === 0}
              className="rounded-md border border-edge px-2.5 py-1 text-sm hover:bg-surface-raised disabled:cursor-not-allowed disabled:opacity-40"
            >
              ← Previous
            </button>
            <button
              type="button"
              onClick={() => go(selected + 1)}
              disabled={selected === total - 1}
              className="rounded-md border border-edge px-2.5 py-1 text-sm hover:bg-surface-raised disabled:cursor-not-allowed disabled:opacity-40"
            >
              Next →
            </button>
            <span className="tabular text-sm text-muted" aria-live="polite">
              Step {selected + 1} of {total}
            </span>
            <span className="ml-auto text-xs text-muted">
              Use ← and → keys
            </span>
          </div>

          <div className="rounded-xl border border-edge bg-surface">
            <div className="flex flex-wrap items-center gap-2 border-b border-edge px-4 py-3">
              <span
                aria-hidden="true"
                className={`flex h-6 w-6 items-center justify-center rounded border text-xs ${style.chip}`}
              >
                {style.glyph}
              </span>
              <h3 className="font-semibold">{step.action_type}</h3>
              {step.action.path && (
                <code className="rounded border border-edge bg-surface-raised px-1.5 py-0.5 font-mono text-xs">
                  {step.action.path}
                </code>
              )}
              {step.tamper_blocked && <TamperBadge />}
              {step.error && (
                <span className="rounded-full border border-failed/40 bg-failed-soft px-2 py-0.5 text-xs text-failed">
                  error
                </span>
              )}
            </div>

            {step.action.content !== undefined && (
              <div className="border-b border-edge px-4 py-3">
                <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                  File the agent wrote
                </h4>
                <CodeBlock content={step.action.content} />
              </div>
            )}

            <div className="px-4 py-3">
              <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                What the environment replied
              </h4>
              <pre className="max-h-96 overflow-auto rounded-lg border border-edge bg-surface-raised p-3 font-mono text-xs whitespace-pre-wrap">
                {step.observation || "(no output)"}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
