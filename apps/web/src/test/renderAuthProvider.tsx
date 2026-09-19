import { ReactElement } from "react";
import { render } from "@testing-library/react";

import { AuthProvider } from "../features/auth/AuthProvider";

export function renderWithProvider(element: ReactElement) {
  return render(<AuthProvider>{element}</AuthProvider>);
}
