import { render, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation, useNavigate } from "react-router-dom";
import { expect } from "vitest";
import { App } from "../app/App";
import { AppProviders } from "../app/AppRoot";
import { testEmail, testPassword } from "./fixtures";

/* MemoryRouter 는 window.location 을 건드리지 않는다 - 주소와 뒤로가기를 보려면
   라우터 안에서 읽어야 한다. 역할(role)이 없는 요소라 기존 쿼리에 끼어들지 않는다. */
function RouteProbe() {
  const location = useLocation();
  const navigate = useNavigate();
  return (
    <span
      data-testid="route-probe"
      data-path={location.pathname}
      data-search={location.search}
      onClick={() => navigate(-1)}
    />
  );
}

export function renderAppRoute(route: string) {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AppProviders>
        <App />
        <RouteProbe />
      </AppProviders>
    </MemoryRouter>,
  );
}

export function routeLocation() {
  const probe = document.querySelector('[data-testid="route-probe"]');
  return {
    pathname: probe?.getAttribute("data-path") ?? "",
    search: probe?.getAttribute("data-search") ?? "",
  };
}

export function goBack() {
  (document.querySelector('[data-testid="route-probe"]') as HTMLElement | null)?.click();
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
