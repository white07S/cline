// MSAL configuration. The SPA performs PKCE flow against Entra ID and
// requests an access token with the SERVER's API scope (not Graph).
// The server validates the resulting JWT via JWKS.

import { type Configuration, PublicClientApplication } from "@azure/msal-browser";

import { env } from "@/env";

if (!env.VITE_AZURE_TENANT_ID || !env.VITE_AZURE_CLIENT_ID || !env.VITE_AZURE_API_SCOPE) {
  // Only crash if MSAL is actually used. In dev without auth, we no-op.
  // Auth-protected routes call ensureMsal() which throws if not configured.
}

const msalConfig: Configuration = {
  auth: {
    clientId: env.VITE_AZURE_CLIENT_ID ?? "00000000-0000-0000-0000-000000000000",
    authority: `https://login.microsoftonline.com/${env.VITE_AZURE_TENANT_ID ?? "common"}`,
    redirectUri: window.location.origin,
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
    storeAuthStateInCookie: false,
  },
};

export const msalInstance = new PublicClientApplication(msalConfig);

export const apiTokenRequest = {
  scopes: env.VITE_AZURE_API_SCOPE ? [env.VITE_AZURE_API_SCOPE] : [],
};

export function ensureMsalConfigured(): void {
  if (!env.VITE_AZURE_CLIENT_ID || !env.VITE_AZURE_TENANT_ID || !env.VITE_AZURE_API_SCOPE) {
    throw new Error(
      "MSAL is not configured. Set VITE_AZURE_TENANT_ID, VITE_AZURE_CLIENT_ID, VITE_AZURE_API_SCOPE.",
    );
  }
}
