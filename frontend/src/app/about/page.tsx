import { Card, PageHeading } from "@/components/layout-bits";

export const metadata = { title: "About" };

export default function AboutPage() {
  return (
    <>
      <PageHeading
        title="What this is"
        lead="AgentGym measures how well an AI agent can fix a bug it has never seen, and makes sure the measurement cannot be gamed."
      />

      <div className="space-y-6 text-sm leading-relaxed">
        <Card title="A reinforcement-learning environment, in plain words">
          <div className="space-y-3 px-4 py-4">
            <p>
              An <strong>environment</strong> is just a world with two buttons.
              One resets it to a fresh starting point; the other takes a single
              action and tells you what happened. That is the whole idea behind
              the classic RL environments — balancing a pole, playing a game —
              and it is the whole idea here too.
            </p>
            <p>
              In AgentGym the world is a small Python project with a bug in it.
              An <strong>episode</strong> is one attempt at one project. The
              agent can list the files, read a file, write a file, run the tests
              it can see, and submit. The ordered list of everything it did is
              the <strong>trajectory</strong> — that is what the replay viewer
              plays back.
            </p>
          </div>
        </Card>

        <Card title="How the score works">
          <div className="space-y-3 px-4 py-4">
            <p>
              The <strong>reward</strong> is zero on every step except the last.
              When the agent submits, the engine throws away the tests the agent
              could run and grades the work against a different set of{" "}
              <strong>hidden tests</strong> — ten to twelve of them per task,
              covering the edge cases. The reward is the fraction that pass.
            </p>
            <p>
              Hiding the grading tests is the point. An agent optimises whatever
              it is measured on, so if it could read the grading tests it could
              special-case them: pass the three examples, fail every other
              input. Because it cannot see them, the cheapest way to score well
              is to write a fix that is actually general.
            </p>
            <p>
              If the hidden tests fail to run at all — a syntax error, a broken
              import — the reward is forced to zero and the episode is recorded
              as an error. Otherwise pytest would report something like
              &ldquo;one test, one error&rdquo; and a crashed submission would
              be credited with a partial score.
            </p>
          </div>
        </Card>

        <Card title="Why there are three scripted agents">
          <div className="space-y-3 px-4 py-4">
            <p>
              A single score for a single model tells you almost nothing. Three
              hard-coded agents give it meaning:
            </p>
            <ul className="ml-5 list-disc space-y-1.5">
              <li>
                <strong>noop</strong> submits immediately. Its reward is
                whatever the buggy code already passes — the floor. An agent
                scoring at or below this did nothing useful.
              </li>
              <li>
                <strong>oracle</strong> applies the reference fix. It must score
                1.000 on every task, which proves each task is solvable and that
                the hidden tests agree with the intended fix. It is a test of the
                task, not a competitor.
              </li>
              <li>
                <strong>tamper</strong> only tries to cheat. Every attempt must
                be refused, and its reward must never exceed noop&rsquo;s. That
                is the anti-reward-hacking claim, checked automatically on every
                run rather than asserted in a readme.
              </li>
            </ul>
          </div>
        </Card>

        <Card title="How cheating is prevented">
          <div className="space-y-3 px-4 py-4">
            <p>
              Every attempt to write a file passes through a guard first. It
              refuses writes to the <code className="font-mono text-xs">tests/</code>{" "}
              folder, writes to files that change how pytest or the interpreter
              behave (<code className="font-mono text-xs">conftest.py</code>,{" "}
              <code className="font-mono text-xs">pytest.ini</code>,{" "}
              <code className="font-mono text-xs">.pth</code> files), paths that
              escape the workspace, and Python files that import things like{" "}
              <code className="font-mono text-xs">subprocess</code> or call{" "}
              <code className="font-mono text-xs">eval</code>.
            </p>
            <p>
              A refused write still costs the agent a step, so probing for holes
              is not free. It is recorded as a tamper attempt and shown in the
              replay with a red badge.
            </p>
            <p>
              Grading happens in a separate directory with the hidden tests
              swapped in, and the test report is written outside that directory
              — so code the agent wrote cannot edit its own grade.
            </p>
          </div>
        </Card>

        <Card title="Threat model: what this does not protect against">
          <div className="space-y-3 px-4 py-4">
            <p>
              Being honest about this matters more than the feature list. The
              guard is a static analysis of the code the agent writes, and tests
              run in a contained subprocess with a wall-clock timeout, a
              stripped-down environment with no API keys in it, and resource
              limits where the operating system provides them.
            </p>
            <p>
              It is <strong>not</strong> a virtual machine or a container.
              Agent-written code runs as the user who started the run, with that
              user&rsquo;s filesystem permissions, and a determined attacker can
              get around static analysis.
            </p>
            <p>
              So the real protection is operational, not technical:{" "}
              <strong>
                untrusted agents only ever run on the machine of whoever started
                them, through the runner on the command line.
              </strong>{" "}
              This dashboard and the API behind it store and serve finished
              results. They never execute anything an agent wrote.
            </p>
          </div>
        </Card>

        <Card title="Reading the outcome labels">
          <div className="px-4 py-4">
            <dl className="space-y-2">
              {[
                ["solved", "Every hidden test passed."],
                [
                  "partial",
                  "Some hidden tests passed — the fix worked for the visible cases but not in general.",
                ],
                [
                  "wrong_fix",
                  "The agent changed files but no hidden test passed.",
                ],
                [
                  "no_change",
                  "The agent never successfully wrote a file. This is what both noop and tamper score.",
                ],
                [
                  "out_of_steps",
                  "The step limit was reached, so the engine submitted on the agent's behalf.",
                ],
                ["timeout", "The tests were killed for running too long."],
                [
                  "error",
                  "The hidden tests could not run, so nothing could be scored.",
                ],
              ].map(([name, meaning]) => (
                <div key={name} className="sm:flex sm:gap-3">
                  <dt className="font-mono text-xs font-semibold sm:w-32 sm:shrink-0 sm:pt-0.5">
                    {name}
                  </dt>
                  <dd className="text-muted">{meaning}</dd>
                </div>
              ))}
            </dl>
          </div>
        </Card>
      </div>
    </>
  );
}
