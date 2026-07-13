import { ReactNode } from "react";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { SessionProvider } from "./session";

export function AppProviders({ children }: { children: ReactNode }) {
  return <SessionProvider>{children}</SessionProvider>;
}

export function AppRoot() {
  return (
    <BrowserRouter>
      <AppProviders>
        <App />
      </AppProviders>
    </BrowserRouter>
  );
}
