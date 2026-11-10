# ADR 0029: Frontend in Next.js with shadcn/ui, built to a committed static export

- **Status**: Accepted
- **Date**: 2026-11-10
- **Supersedes**: the **Frontend**, **CSS build** and **Static assets are local** bullets of [0005](0005-technology-stack-and-conventions.md) (the backend, FLAC, Discogs, style and error bullets stand)

## Context

The owner prefers the look of a shadcn/ui interface (a pastel card board with a sidebar) and asked for the whole frontend to move to it. A prototype built against a scratch instance showed that the existing screens port one to one. The single `index.html` (870 lines of string-built DOM) was hard to extend; typed components make the dialogs and their state easier to keep correct.

The Docker image and `./app.py` must keep working without Node at run time ([0003](0003-deployment-web-app-in-docker.md), and the earlier decision to commit `static/app.css`).

## Decision

- **Source** in `ui/`: Next.js (App Router), React, TypeScript, Tailwind CSS v4 and shadcn/ui components (Radix primitives, lucide icons, sonner toasts), Geist font loaded at build time (no runtime request to Google Fonts, so the Inter exception of 0005 is gone). Code style follows 0005: tabs, single quotes.
- **Static export, no Node at run time**: `next.config.ts` sets `output: 'export'` and `assetPrefix: '/static/ui'`. `cd ui && npm run build` writes the export to `static/ui/`, which **is committed** (like `static/app.css` was). `app.py` serves `static/ui/index.html` at `/`; everything else of the frontend is under `/static/ui/`. No server-side rendering, no Next.js server, no Node in the Docker image.
- **One page**: the app is a single client-side page (no routes). It talks to the existing `/api/*` endpoints only; this ADR adds or changes no endpoint.
- **Development**: `cd ui && npm install && npm run dev` serves the UI on port 3000 and proxies `/api` to `TAGWRIGHT_API` (default `http://localhost:8080`); the rewrite exists only in development. Per [0018](0018-verification.md) point it at a scratch instance.
- **Dependencies** are pinned by `ui/package-lock.json`. `ui/node_modules/`, `ui/.next/` and `ui/out/` are never committed. A new npm dependency needs a mention in the commit message; a new framework needs an ADR.
- **Rebuild rule**: every change under `ui/` that affects what the browser loads is rebuilt (`npm run build`) and the resulting `static/ui/` is committed in the same commit.
- **Static icons** stay in `static/` (`icon.svg`, `discogs.png`, `musicbrainz.ico`, `lrclib.ico`, `musichoarders.svg`, `albumartexchange.ico`) and are referenced as `/static/<file>`. They remain sent with `Cache-Control: no-cache`.
- **Removed**: `index.html`, `static/app.css`, `ui/app.in.css` and the daisyUI theme `fixer`.

## Consequences

- `app.py` stays the only server file; the frontend is no longer a single file. The "one-file frontend" rule of [0005](0005-technology-stack-and-conventions.md) and `AGENTS.md` is replaced by this ADR.
- Rebuilding changes many hashed files under `static/ui/` in each frontend commit; the diff of `ui/` is the reviewable part.
- Building needs Node 20 or newer on the developer machine; running does not.
- Layout, colours and dialogs: [0030](0030-ui-layout-and-design-system-v2.md).
