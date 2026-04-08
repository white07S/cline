import { MsalProvider } from "@azure/msal-react";
import type { ReactNode } from "react";

import { msalInstance } from "./msal";

type Props = { children: ReactNode };

export function AuthProvider({ children }: Props) {
  return <MsalProvider instance={msalInstance}>{children}</MsalProvider>;
}
