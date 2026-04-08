// Zod-validated environment variables. Import meta.env is `unknown` until
// parsed here, then the rest of the codebase imports `env` (typed).

import { z } from "zod";

const EnvSchema = z.object({
  VITE_API_BASE_URL: z.string().url(),
  VITE_AZURE_TENANT_ID: z.string().min(1).optional(),
  VITE_AZURE_CLIENT_ID: z.string().min(1).optional(),
  VITE_AZURE_API_SCOPE: z.string().min(1).optional(),
  VITE_SENTRY_DSN: z.string().url().optional(),
});

export type Env = z.infer<typeof EnvSchema>;

const parsed = EnvSchema.safeParse(import.meta.env);
if (!parsed.success) {
  // Fail loudly at startup. NEVER fall through with a partial env.
  console.error("Invalid environment variables:", parsed.error.flatten().fieldErrors);
  throw new Error("Invalid environment configuration — see console for details");
}

export const env: Env = parsed.data;
