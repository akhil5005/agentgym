/**
 * The shape of everything the backend serves.
 *
 * These mirror the Pydantic response models in `backend/app/schemas.py`. They
 * are hand-written rather than generated so you can read the API contract in
 * one file, but they must be kept in step with that file.
 */

export type Difficulty = "easy" | "medium" | "hard";

/** Every outcome the engine can record. See `classify_outcome` in env.py. */
export type Outcome =
  | "solved"
  | "partial"
  | "wrong_fix"
  | "no_change"
  | "out_of_steps"
  | "timeout"
  | "error";

/** The five things an agent can do. */
export type ActionType =
  | "list_files"
  | "read_file"
  | "write_file"
  | "run_tests"
  | "submit"
  /** Recorded when an agent sent something the environment could not parse. */
  | "invalid";

export interface Task {
  id: string;
  title: string;
  difficulty: Difficulty;
  category: string;
  description: string;
  max_steps: number;
  episodes: number;
  solve_rate: number;
  mean_reward: number;
  mean_steps: number;
}

export interface Step {
  index: number;
  action_type: ActionType | string;
  /** The raw action. `path` and `content` are present only for file actions. */
  action: { type?: string; path?: string; content?: string };
  observation: string;
  reward: number;
  error: boolean;
  tamper_blocked: boolean;
  created_at: string;
}

export interface EpisodeSummary {
  id: string;
  task_id: string;
  agent_name: string;
  model: string | null;
  trial: number;
  reward: number;
  outcome: Outcome | string;
  steps_used: number;
  tamper_attempts: number;
  tests_passed: number;
  tests_total: number;
  started_at: string;
  finished_at: string;
}

export interface EpisodeDetail extends EpisodeSummary {
  steps: Step[];
}

export interface LeaderboardRow {
  agent_name: string;
  model: string | null;
  /** `agent_name (model)`, or just the name for scripted agents. */
  label: string;
  episodes: number;
  mean_reward: number;
  solve_rate: number;
  mean_steps: number;
  /** Share of this agent's episodes containing at least one blocked write. */
  tamper_rate: number;
}

export interface MatrixCell {
  task_id: string;
  label: string;
  /** `label` split in two, so the header can put the model on its own line. */
  agent_name: string;
  model: string | null;
  n: number;
  solve_rate: number;
  mean_reward: number;
}

export interface Stats {
  tasks: number;
  episodes: number;
  agents: number;
}
