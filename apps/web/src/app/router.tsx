import { BrowserRouter } from "react-router-dom";

import { AppShell } from "./AppShell";

export function AppRouter() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
