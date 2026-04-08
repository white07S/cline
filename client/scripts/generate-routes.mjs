#!/usr/bin/env node
// Standalone TanStack Router route-tree generator.
//
// Background: src/routeTree.gen.ts is normally produced as a side effect of
// `vite dev` / `vite build` via the @tanstack/router-vite-plugin. The file is
// gitignored on purpose (it's generated), which means a fresh checkout — for
// example, the GitHub Actions runner — has no route tree on disk. `tsc --noEmit`
// then fails because src/main.tsx imports `@/routeTree.gen`. CI runs the
// typecheck step BEFORE the build step, so we cannot rely on Vite producing it.
//
// This script invokes the same `Generator` class the Vite plugin uses, with the
// same config the plugin reads from vite.config.ts. Run it from CI before tsc
// (and feel free to run it locally if you prefer not to keep `vite dev` open).

import { Generator, getConfig } from "@tanstack/router-generator";

const root = process.cwd();

// Mirrors the options passed to TanStackRouterVite() in vite.config.ts. If
// those move, update them here too — there is no shared source for them.
const userConfig = getConfig(
  {
    routesDirectory: "./src/routes",
    generatedRouteTree: "./src/routeTree.gen.ts",
  },
  root,
);

const generator = new Generator({ config: userConfig, root });
await generator.run();
// biome-ignore lint/suspicious/noConsoleLog: build script, console output is the intent
console.log("✓ generated", userConfig.generatedRouteTree);
