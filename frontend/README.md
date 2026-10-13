# AgentGym dashboard

The Next.js front end. See the [project README](../README.md) for what AgentGym
is and how the pieces fit together.

## Running it

The dashboard reads everything from the API, so start that first:

```bash
# from the repository root
uvicorn app.main:app --reload --app-dir backend
```

Then, in this folder:

```bash
npm install
cp .env.example .env.local        # only needed if the API is not on :8000
npm run dev                       # http://localhost:3000
```

## Checks

```bash
npx tsc --noEmit     # types
npm run lint         # eslint
npm run build        # production build
```

If you add a route, run `npx next typegen` so the generated `PageProps<"/...">`
helpers know about it.

## Layout

| Path | What it holds |
| --- | --- |
| `src/lib/types.ts` | The API's response shapes, mirroring `backend/app/schemas.py` |
| `src/lib/api.ts` | Every fetch call. Returns `null` instead of throwing when the API is down |
| `src/components/` | Tables, badges, and the replay viewer |
| `src/app/` | The five pages: overview, tasks, task detail, episode replay, about |

Pages are server components and read data on each request. The replay viewer is
the one client component, because it holds the selected-step state.
