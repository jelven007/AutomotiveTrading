import { BrowserRouter } from "react-router-dom";

import { LocalWorkspaceProvider } from "../features/auth/LocalWorkspaceProvider";
import { AppShell } from "./AppShell";

export function AppRouter() {
  return (
    <BrowserRouter>
      <LocalWorkspaceProvider>
        <AppShell />
      </LocalWorkspaceProvider>
    </BrowserRouter>
  );
}
