import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { expect } from "vitest";
import { App } from "../app/App";
import { AppProviders } from "../app/AppRoot";
import { testEmail, testPassword } from "./fixtures";

export function renderAppRoute(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders>
        <App />
      </AppProviders>
    </MemoryRouter>,
  );
}

export function getLink(href: string) {
  const expectedHref = decodeURIComponent(href);
  const link = Array.from(document.querySelectorAll("a")).find((candidate) => {
    const candidateHref = candidate.getAttribute("href") ?? "";
    return (
      candidateHref === href ||
      decodeURIComponent(candidateHref) === expectedHref
    );
  });
  expect(link).toBeTruthy();
  return link as HTMLAnchorElement;
}

export async function login() {
  const user = userEvent.setup();
  renderAppRoute("/login");
  await user.type(
    document.querySelector('input[name="email"]') as HTMLInputElement,
    testEmail,
  );
  await user.type(
    document.querySelector('input[name="password"]') as HTMLInputElement,
    testPassword,
  );
  const submit = document.querySelector('button[type="submit"]');
  expect(submit).toBeTruthy();
  await user.click(submit as HTMLButtonElement);
  await waitFor(() => expect(getLink("/policies")).toBeInTheDocument());
}
