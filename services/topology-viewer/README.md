# Topology viewer

Interactive, browser-based view of the platform topology (React Flow). The machine-readable graph lives in [`public/topology.json`](public/topology.json); narrative and integration rules remain in the repo root [`docs/TOPOLOGY.md`](../../docs/TOPOLOGY.md).

## Run locally (dev)

```bash
npm install
npm run dev --workspace=topology-viewer
```

Open the URL Vite prints (default `http://localhost:5173`). The app loads `topology.json` from the dev server.

## Build

```bash
npm run build --workspace=topology-viewer
```

Output is in `dist/`, including `topology.json` copied from `public/`.

## Ship behind Birtha API (`/ui/topology/`)

The FastAPI app serves static files under `/ui` from [`services/api/src/static`](../api/src/static). After you change the viewer or `topology.json`, rebuild and copy:

```bash
npm run deploy-api-static --workspace=topology-viewer
```

This runs `vite build` with `base: /ui/topology/` and copies `dist/` into `services/api/src/static/topology/`. Then open `http://localhost:8080/ui/topology/` (or your API host) when the API container is up.

## Keeping docs and JSON in sync

Architecture changes that affect service boundaries should update **`docs/TOPOLOGY.md` first** (per that document’s policy), then update **`public/topology.json`** in the same change so the interactive viewer and the written spec stay aligned.

## Data shape

Types and Zod parsing live in `src/topology/`. Views in JSON provide layer tabs (system, orchestrator, workers, models, tools, data, observability). Each view must only reference node ids that exist on that view’s `nodes` list.
