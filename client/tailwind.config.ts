// Tailwind v4 — most config now lives in CSS via @theme.
// This file is kept minimal for tooling that still expects it.
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
} satisfies Config;
