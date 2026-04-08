// ESLint config — INTENTIONALLY MINIMAL.
// Biome handles formatting and most linting. ESLint is here ONLY for
// eslint-plugin-react-hooks (rules-of-hooks + exhaustive-deps), which Biome
// does not yet have full equivalents for. Do not add other plugins here
// without discussion.
//
// We pull in @typescript-eslint/parser solely so ESLint can read .ts/.tsx —
// no @typescript-eslint rules are enabled. mypy-style type checking is the
// TypeScript compiler's job (see `bunx tsc --noEmit`).

import tsParser from "@typescript-eslint/parser";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: 2023,
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
      globals: { ...globals.browser },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      "react-hooks/exhaustive-deps": "warn",
    },
  },
  {
    ignores: [
      "dist/**",
      "node_modules/**",
      "src/routeTree.gen.ts",
      "src/api/types.gen.ts",
      "playwright-report/**",
      "test-results/**",
    ],
  },
];
