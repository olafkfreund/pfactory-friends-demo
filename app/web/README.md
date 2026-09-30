# app/web

MyFriends frontend — React + TypeScript + Vite. One screen (`src/App.tsx`)
that fetches `GET /profiles/me` and renders it, with loading and error
states.

```sh
npm install
npm run dev        # local dev server
npm run typecheck  # tsc -b
npm test           # vitest run
npm run build      # static assets to dist/
```

`Dockerfile` builds the static assets and serves them via nginx, proxying
`/healthz` and `/profiles/` to the `myfriends-api` Service (see
`nginx.conf`).
