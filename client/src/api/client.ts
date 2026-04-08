// Configured Axios instance. Adds:
//   - Authorization: Bearer <token> from MSAL
//   - X-Request-ID for trace correlation with the server
//   - Maps AxiosError → typed ApiError
//
// ALWAYS import `apiClient` from this module. Never `new Axios()` elsewhere.

import { InteractionRequiredAuthError } from "@azure/msal-browser";
import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from "axios";
import { v4 as uuidv4 } from "uuid";

import { apiTokenRequest, msalInstance } from "@/auth/msal";
import { env } from "@/env";

// ── Typed error ────────────────────────────────────────────────

export interface ApiErrorBody {
  detail?: string;
  message?: string;
  code?: string;
}

export class ApiError extends Error {
  public readonly status: number;
  public readonly code: string | undefined;
  public readonly requestId: string | undefined;

  constructor(message: string, status: number, code?: string, requestId?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.requestId = requestId;
  }
}

// ── Token acquisition ──────────────────────────────────────────

async function acquireToken(): Promise<string | null> {
  const accounts = msalInstance.getAllAccounts();
  if (accounts.length === 0) return null;

  try {
    const result = await msalInstance.acquireTokenSilent({
      ...apiTokenRequest,
      account: accounts[0],
    });
    return result.accessToken;
  } catch (e) {
    if (e instanceof InteractionRequiredAuthError) {
      // Caller (a route guard) should redirect to login.
      throw e;
    }
    throw e;
  }
}

// ── Axios instance ─────────────────────────────────────────────

export const apiClient: AxiosInstance = axios.create({
  baseURL: env.VITE_API_BASE_URL,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

apiClient.interceptors.request.use(async (config: InternalAxiosRequestConfig) => {
  config.headers.set("X-Request-ID", uuidv4());

  const token = await acquireToken();
  if (token) {
    config.headers.set("Authorization", `Bearer ${token}`);
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    const status = error.response?.status ?? 0;
    const body = error.response?.data;
    const message = body?.detail ?? body?.message ?? error.message ?? "Request failed";
    const code = body?.code;
    const requestId =
      typeof error.config?.headers?.get === "function"
        ? (error.config.headers.get("X-Request-ID") as string | undefined)
        : undefined;

    // Surface structured error and re-throw — no silent swallow.
    throw new ApiError(message, status, code, requestId);
  },
);
