# Deploying AgentGym

Three free-tier services, no Docker, no Terraform, no AWS:

| Piece | Where | What it does |
| --- | --- | --- |
| Database | [Neon](https://neon.tech) | Postgres, holds tasks and episodes |
| Backend | [Render](https://render.com) | FastAPI, stores and serves results |
| Frontend | [Vercel](https://vercel.com) | The Next.js dashboard |

**Episodes still run on your own machine.** Nothing you deploy ever executes
agent-written code — you run the episodes locally with the runner CLI and upload
the finished results. That split is the project's actual security boundary, so
do not try to "helpfully" move the runner onto the server.

> These providers change their dashboards and free-tier limits regularly. The
> steps below were accurate when written; if a screen does not match, check the
> provider's own current docs rather than hunting for the button described here.

---

## 1. Database on Neon

1. Create an account and a new project. Any region near you is fine.
2. From the project dashboard, copy the **connection string**. It looks like:
   ```
   postgresql://user:password@ep-something-123456.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
3. Keep it somewhere safe for the next step. Treat it as a password — it is one.

You do not need to create any tables. The backend creates them on startup.

Neon's free tier suspends a database that has been idle for a few minutes. The
first request after that wakes it, which takes a second or two.

---

## 2. Backend on Render

1. Push this repository to GitHub.
2. In Render, choose **New → Web Service** and connect the repository.
3. Configure it:

   | Setting | Value |
   | --- | --- |
   | Root directory | `backend` |
   | Runtime | Python 3 |
   | Build command | `pip install -r requirements.txt` |
   | Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | Instance type | Free |

   `$PORT` is set by Render. Do not hard-code a port number.

4. **Pin the Python version.** Add an environment variable
   `PYTHON_VERSION` = `3.13.7` (or whatever `python --version` prints locally).
   Without it Render picks its own default, which may be older than the 3.11
   this project needs.

5. Set the rest of the environment variables:

   | Name | Value |
   | --- | --- |
   | `ENV` | `prod` |
   | `DATABASE_URL` | the Neon connection string from step 1 |
   | `INGEST_API_KEY` | a long random string you generate |
   | `FRONTEND_ORIGIN` | your Vercel URL, e.g. `https://agentgym.vercel.app` |

   Generate the key with:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   With `ENV=prod` the app **refuses to start** if `INGEST_API_KEY` is still the
   default `dev-key`. That is deliberate: failing loudly at startup beats
   running with a publicly known key.

   You will not know the Vercel URL until step 3. Put a placeholder in now and
   come back to correct it — until it matches, the browser will block the
   dashboard's requests with a CORS error.

6. Deploy, then check it:
   ```bash
   curl https://your-service.onrender.com/api/health
   # {"status":"ok"}
   ```
   Also open `https://your-service.onrender.com/docs` for the generated API docs.

Render's free tier sleeps a service after about 15 minutes of no traffic. The
next request wakes it and can take 30 seconds or more. That is normal, and it is
why the dashboard shows a loading state rather than failing.

---

## 3. Frontend on Vercel

1. In Vercel, **Add New → Project**, and import the same repository.
2. Configure it:

   | Setting | Value |
   | --- | --- |
   | Root directory | `frontend` |
   | Framework preset | Next.js (detected automatically) |
   | Build command | default |

3. Add one environment variable:

   | Name | Value |
   | --- | --- |
   | `NEXT_PUBLIC_API_URL` | `https://your-service.onrender.com` |

   No trailing slash. The `NEXT_PUBLIC_` prefix is required for Next.js to
   expose it to the build.

4. Deploy. Then go back to Render and set `FRONTEND_ORIGIN` to the Vercel URL
   you were just given, and redeploy the backend so CORS allows it.

---

## 4. Upload your results

Everything above is empty until you send it some data. From your own machine,
in the repository root with the virtualenv active:

```bash
export AGENTGYM_API=https://your-service.onrender.com
export AGENTGYM_KEY=the-ingest-key-you-generated      # same value as on Render

# Task metadata first — episodes reference tasks, so this has to come first.
python -m agentgym.runner sync-tasks --api "$AGENTGYM_API" --key "$AGENTGYM_KEY"

# Then the results.
python -m agentgym.runner run --agent oracle --tasks all --out runs/oracle.jsonl \
  --api "$AGENTGYM_API" --key "$AGENTGYM_KEY"
python -m agentgym.runner run --agent noop   --tasks all --out runs/noop.jsonl \
  --api "$AGENTGYM_API" --key "$AGENTGYM_KEY"
python -m agentgym.runner run --agent tamper --tasks all --out runs/tamper.jsonl \
  --api "$AGENTGYM_API" --key "$AGENTGYM_KEY"
```

On PowerShell, use `$env:AGENTGYM_API = "https://..."` instead of `export`.

If the upload fails partway — the free tier was asleep, the wifi dropped — the
run files are still on disk and re-uploading is safe:

```bash
python -m agentgym.runner upload "runs/*.jsonl" --api "$AGENTGYM_API" --key "$AGENTGYM_KEY"
```

Episodes already stored come back as "already present" rather than being
duplicated, so you can run that as many times as you like.

`sync-tasks` uploads only each task's id, title, difficulty, category,
description and step limit. **Hidden tests, reference solutions and the hidden
test count never leave your machine.** That is enforced in code by
`Task.public_dict()`, not by remembering to be careful.

---

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Dashboard shows "Could not load the results" | Backend asleep (wait and reload) or `NEXT_PUBLIC_API_URL` is wrong |
| Browser console shows a CORS error | `FRONTEND_ORIGIN` on Render does not exactly match the Vercel URL |
| Backend will not start, logs mention `INGEST_API_KEY` | `ENV=prod` with the key still set to `dev-key` |
| Upload returns 401 | `--key` does not match `INGEST_API_KEY` on Render |
| Upload returns 400 saying "unknown task" | Run `sync-tasks` before uploading episodes |
| Backend logs a psycopg import error | `DATABASE_URL` was not copied completely |

The backend rewrites a `postgres://` or `postgresql://` prefix to
`postgresql+psycopg://` for you, so paste Neon's string exactly as given.

---

## Costs

All three free tiers are enough for this project: the database is a few hundred
kilobytes, the API serves a handful of requests, and the dashboard is mostly
static. The only thing that costs money is running the LLM agent, which happens
on your machine and is billed by Anthropic per token.
