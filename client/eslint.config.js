// ESLint config — INTENTIONALLY MINIMAL.
// Biome handles formatting and most linting. ESLint is here ONLY for
// eslint-plugin-react-hooks (rules-of-hooks + exhaustive-deps), which Biome
// does not yet have full equivalents for. Do not add other plugins here
// without discussion.

import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";

export default [
  {
    files: ["src/**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
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
