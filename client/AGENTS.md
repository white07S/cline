# `client/` — agent guide

React SPA for the data platform. Bundled by Vite (Rolldown), managed by Bun.

## Stack

| Concern | Choice |
|---|---|
| Runtime / package manager | **Bun 1.2+** (`bun install`, `bun run`) |
| Bundler / dev server | **Vite 8** with Rolldown (Rust-based, replaces Rollup) |
| Framework | React 19 + TypeScript (strict) |
| Routing | **TanStack Router** v1 (file-based, fully type-safe) |
| Server state | **TanStack Query** v5 |
| Forms | **TanStack Form** v1 (no Formik, no react-hook-form) |
| Validation | **Zod** v3 |
| Styling | **Tailwind v4** |
| HTTP | **Axios** with MSAL token interceptor |
| Auth | **@azure/msal-browser** + **@azure/msal-react** (PKCE flow) |
| Lint / format | **Biome** (single tool, replaces Prettier + most of ESLint) + minimal **ESLint** for `react-hooks` rules only |
| Tests (unit/component) | **Vitest** + **@testing-library/react** + **jsdom** |
| Tests (e2e) | **Playwright** |
| API types | Generated from server `openapi.json` via `openapi-typescript` (run `just openapi`) |
| Icons | TBD — `lucide-react` is the default |

**No XState.** Removed during planning — TanStack Query already handles the async state needs of this app, and adding XState was unjustified complexity. If a genuine state-machine need arises later (multi-step wizard, complex chat session lifecycle), revisit.

## Layout

```
client/
├── package.json
├── bunfig.toml
├── tsconfig.json
├── vite.config.ts
├── biome.json
├── eslint.config.js              # ONLY react-hooks rules
├── tailwind.config.ts
├── postcss.config.js
├── vitest.config.ts
├── playwright.config.ts
├── index.html
├── Dockerfile                    # Multi-stage: build → nginx static
└── src/
    ├── main.tsx                  # entry; mounts <App />
    ├── routes/                   # TanStack Router file-based routes
    │   ├── __root.tsx
    │   └── index.tsx
    ├── routeTree.gen.ts          # GENERATED — do not edit
    ├── api/
    │   ├── client.ts             # axios instance + MSAL token interceptor
    │   ├── openapi.json          # GENERATED — do not edit
    │   ├── types.gen.ts          # GENERATED — do not edit
    │   └── queries/              # TanStack Query hooks
    ├── auth/
    │   ├── msal.ts               # MSAL config
    │   └── AuthProvider.tsx      # MsalProvider wrapper
    ├── components/               # Reusable presentational components
    ├── features/                 # Feature-sliced — one folder per feature
    ├── lib/                      # Pure utils (date, format, zod helpers)
    ├── styles/
    │   └── globals.css           # Tailwind directives + design tokens
    └── env.ts                    # Zod-validated import.meta.env
```

## Universal best practices (mandatory)

These restate the rules from the root `README.md`. Reviewed on every PR.

### 1. Strict typesafety, no `any`

**`any` is banned.** Biome and `tsc --strict` enforce it. The escape hatches that look harmless are also banned:

```ts
// ❌ NEVER
function handle(payload: any) { ... }
const data: any = await res.json()
const x = anything as any
type Foo = { [key: string]: any }
function handle(payload: Record<string, any>) { ... }   // same thing
function handle(payload: object) { ... }                // also banned — too loose
function handle(payload: {}) { ... }                    // also banned

// ✅ ALWAYS
const Schema = z.object({ id: z.string().uuid(), email: z.string().email() })
type Payload = z.infer<typeof Schema>
function handle(payload: Payload) { ... }

// For data crossing the network boundary, validate at the boundary:
const raw = await res.json()                            // unknown
const parsed = Schema.parse(raw)                        // typed Payload
```

The pattern: **anything that crosses a boundary** (network, localStorage, postMessage, URL params) is `unknown` until parsed by a Zod schema. Once parsed, the rest of the codebase sees a fully-typed value.

API response types live in `src/api/types.gen.ts`, generated from the server's OpenAPI schema. **Never hand-write a type that the server already exposes.** Run `just openapi` after any server schema change.

### 2. No silent error bypass

```ts
// ❌ NEVER
try {
  await api.createUser(data)
} catch {
  // swallowed — bug becomes invisible
}

try {
  await api.createUser(data)
} catch (e) {
  console.log(e)        // logging without re-raising is the same thing
}

// ✅ ALWAYS — TanStack Query handles error state. Throw and let it propagate.
const mutation = useMutation({
  mutationFn: (data: CreateUserIn) => api.createUser(data),
  onError: (err) => toast.error(formatError(err)),
})
```

The only case where catching an error and not re-raising is acceptable is when you have an explicit recovery path AND you log the original error. Even then, prefer `try { ... } catch (e) { log(e); throw new DomainError(...) }`.

### 3. Explicit error types at every boundary

- HTTP errors → `AxiosError` is intercepted in `src/api/client.ts` and rethrown as a typed `ApiError`.
- Zod parse failures → caught at the boundary, mapped to a user-facing error message via `formatZodError`.
- MSAL errors → handled by the interceptor; `InteractionRequiredAuthError` triggers re-login.

### 4. Async vs concurrent — be deliberate

- React's render cycle is **synchronous**. Async work happens in event handlers and effects.
- For data fetching, **use TanStack Query**. Don't roll your own `useState + useEffect + fetch`.
- For multiple parallel requests, use `useQueries` or `Promise.all` — but only when the requests are **genuinely independent**. If one request depends on another's response, sequence them with `enabled: !!firstResult`.

```tsx
// ❌ Reflex parallelism
const [a, b, c] = await Promise.all([fetchA(), fetchB(), fetchC(id)])
//                                                            ^^ depends on what?

// ✅ Sequential when there's a dependency
const a = useQuery({ queryKey: ['a'], queryFn: fetchA })
const b = useQuery({
  queryKey: ['b', a.data?.id],
  queryFn: () => fetchB(a.data!.id),
  enabled: !!a.data,
})
```

### 5. Ask, don't guess

If a server response shape is unclear, an MSAL config option's effect is unknown, or a design intent is ambiguous — **stop and ask**. Don't reverse-engineer from a partial example.

## Routing

TanStack Router uses file-based routes. The file `src/routes/__root.tsx` is the root layout. Adding a route is "create a file in `src/routes/`" — the route tree is generated into `src/routeTree.gen.ts` automatically by the Vite plugin in dev mode.

- Routes are **fully typed** — params, search, loader data are all inferred.
- Use `beforeLoad` for auth guards. The MSAL session is checked there, not in component render.
- Loaders should call TanStack Query (`queryClient.ensureQueryData`), not bare fetch.

## API client

`src/api/client.ts` exports a configured Axios instance. It:
1. Adds `Authorization: Bearer <token>` from MSAL on every request.
2. Adds `X-Request-ID` (uuid) for trace correlation with the server.
3. Catches 401s and triggers MSAL re-auth.
4. Maps `AxiosError` → typed `ApiError` in a response interceptor.

Always import `client` from this module — never instantiate Axios directly elsewhere.

## Auth (MSAL, BFF-ish)

The SPA performs the MSAL PKCE flow against Entra ID. The token it receives has the **server's API scope** (not Microsoft Graph). The server validates this token via JWKS.

This is **not** a strict BFF (which would have zero MSAL in the client and rely on a server-side session cookie). If we ever need to switch to strict BFF, the migration is: drop msal-browser, replace with cookie-based session endpoints on the server. Plan that as its own work.

## Styling

- Tailwind v4. Design tokens live in `src/styles/globals.css` via `@theme`.
- No CSS-in-JS. No CSS modules.
- Components compose Tailwind classes. Variant logic uses `clsx` (or `tailwind-variants` if it grows).

## Testing

```bash
just test-client      # vitest run, single pass
bun run test:watch    # vitest in watch mode
just e2e              # playwright (requires dev stack to be running)
```

- Unit tests live next to the code: `Foo.tsx` + `Foo.test.tsx`.
- Use `@testing-library/react` for component tests.
- **No mocking the API client.** Use MSW (Mock Service Worker) at the network layer instead — it gives you realistic request/response handling.
- Playwright tests live in `tests/e2e/`.

## Linting tools — why two?

- **Biome** does ~95% of what we need: format, basic lint, import sorting, ~80% of common ESLint rules.
- **ESLint** is kept ONLY for `eslint-plugin-react-hooks`. Those two rules (`rules-of-hooks` and `exhaustive-deps`) catch real bugs and Biome doesn't have full equivalents yet (as of 2026). Both run in CI; both run in pre-commit.

If you find yourself wanting to add an ESLint plugin, **ask first**. The two-tool setup is a deliberate compromise — adding more ESLint plugins erodes the speed advantage of Biome.

## Common gotchas

- **`routeTree.gen.ts` is generated.** Don't edit it by hand. Don't commit it (it's gitignored). Vite plugin regenerates it on save.
- **Tailwind v4 uses `@import "tailwindcss"`** in CSS, not the old three `@tailwind` directives.
- **Bun's test runner ≠ Vitest.** We use `bunx vitest`, not `bun test`. Bun's runner doesn't handle React component tests as well.
- **Vite hot reload requires single dev process.** If you're running both `bun run dev` and the docker `client` service, port 5173 will collide.
- **MSAL 4.x requires HTTPS in production** — localhost is the only HTTP exception.
