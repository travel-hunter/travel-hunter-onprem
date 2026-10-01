import { CalendarDays, Home, ShieldCheck, UserRound, WalletCards } from "lucide-react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useSession } from "../app/session";

export function PublicLayout() {
  const { pathname } = useLocation();
  const isPrototypeLoginScreen =
    pathname === "/" ||
    pathname === "/login" ||
    pathname === "/signup" ||
    pathname === "/forgot-password" ||
    pathname === "/reset-password" ||
    pathname === "/oauth/callback" ||
    pathname === "/onboarding";

  return (
    <main className={isPrototypeLoginScreen ? "public-layout prototype-login-layout" : "public-layout"}>
      <div className={isPrototypeLoginScreen ? "public-container prototype-login-container" : "public-container"}>
        <Outlet />
      </div>
    </main>
  );
}

export function ServiceLayout() {
  return (
    <div className="service-layout">
      <TopNavigation />
      <main className="app-container">
        <Outlet />
      </main>
      <BottomTabs />
    </div>
  );
}

function tabClass({ isActive }: { isActive: boolean }) {
  return isActive ? "tab active" : "tab";
}

function topTabClass({ isActive }: { isActive: boolean }) {
  return isActive ? "top-tab active" : "top-tab";
}

/* 넓은 화면 위 메뉴(시안 v41): 빨간 글씨 이름 · 글자 탭(고른 탭은 굵게, 아래 밑줄) · 오른쪽 끝 '내 정보'.
   관리자는 '내 정보' 앞. 오른쪽 무리의 첫 탭이 .push 로 남은 폭을 밀어낸다 */
function TopNavigation() {
  const { currentUser } = useSession();
  const isAdmin = currentUser?.role === "admin";
  const pushed = (state: { isActive: boolean }) => `${topTabClass(state)} push`;
  return (
    <header className="service-top-navigation" aria-label="데스크톱 주요 메뉴">
      <span className="service-top-brand">트래블헌터</span>
      <nav className="top-tabs" aria-label="주요 메뉴">
        <NavLink className={topTabClass} to="/home">
          <span>홈</span>
        </NavLink>
        <NavLink className={topTabClass} to="/policies">
          <span>정책</span>
        </NavLink>
        <NavLink className={topTabClass} to="/trips">
          <span>일정</span>
        </NavLink>
        {isAdmin && (
          <NavLink className={pushed} to="/admin">
            <span>관리자</span>
          </NavLink>
        )}
        <NavLink className={isAdmin ? topTabClass : pushed} to="/mypage">
          <span>내 정보</span>
        </NavLink>
      </nav>
    </header>
  );
}

export function BottomTabs() {
  const { currentUser } = useSession();
  const isAdmin = currentUser?.role === "admin";
  return (
    <nav className={isAdmin ? "bottom-tabs admin-tabs" : "bottom-tabs"} aria-label="주요 메뉴">
      <NavLink className={tabClass} to="/home">
        <Home size={19} />
        <span>홈</span>
      </NavLink>
      <NavLink className={tabClass} to="/policies">
        <WalletCards size={19} />
        <span>정책</span>
      </NavLink>
      <NavLink className={tabClass} to="/trips">
        <CalendarDays size={19} />
        <span>일정</span>
      </NavLink>
      <NavLink className={tabClass} to="/mypage">
        <UserRound size={19} />
        <span>마이</span>
      </NavLink>
      {isAdmin && (
        <NavLink className={tabClass} to="/admin">
          <ShieldCheck size={19} />
          <span>관리자</span>
        </NavLink>
      )}
    </nav>
  );
}
