import { ReactNode, useEffect } from "react";
import { BrowserRouter } from "react-router-dom";
import { purgeStaleDrafts } from "../utils/draftStorage";
import { App } from "./App";
import { SessionProvider } from "./session";

export function AppProviders({ children }: { children: ReactNode }) {
  // 앱을 켤 때 한 번 - 예전 판 초안(1판 장소 수정 초안에는 카카오 이름 · 메모가 있다)을 지운다. 경로 시험도 이 래퍼를 거친다
  useEffect(() => {
    purgeStaleDrafts();
  }, []);
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
