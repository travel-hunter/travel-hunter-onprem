import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach } from "vitest";
import { NO_CONDITIONS, setPolicyConditions } from "../components/map/policyConditions";
import { forgetSheetMemory } from "../components/map/sheetMemory";

function installMemoryLocalStorage() {
  const values = new Map<string, string>();
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      get length() {
        return values.size;
      },
      clear: () => values.clear(),
      getItem: (key: string) => values.get(key) ?? null,
      key: (index: number) => Array.from(values.keys())[index] ?? null,
      removeItem: (key: string) => {
        values.delete(key);
      },
      setItem: (key: string, value: string) => {
        values.set(key, String(value));
      },
    },
  });
}

function hasUsableLocalStorage() {
  try {
    const storage = window.localStorage;
    if (
      typeof storage?.clear !== "function" ||
      typeof storage.getItem !== "function" ||
      typeof storage.removeItem !== "function" ||
      typeof storage.setItem !== "function"
    ) {
      return false;
    }
    const probeKey = "__travel_hunter_vitest_storage_probe__";
    storage.setItem(probeKey, "ok");
    const canReadWrite = storage.getItem(probeKey) === "ok";
    storage.removeItem(probeKey);
    storage.clear();
    return canReadWrite;
  } catch {
    return false;
  }
}

function ensureLocalStorage() {
  if (!hasUsableLocalStorage()) {
    installMemoryLocalStorage();
  }
}

beforeEach(() => {
  ensureLocalStorage();
});

afterEach(() => {
  // 정책 탭 좁히기 조건은 모듈 밖 저장소(sessionStorage)에 산다 - 시험끼리 새지 않게 비운다
  setPolicyConditions(NO_CONDITIONS);
  // 목록 시트의 스크롤 자리 · 여닫은 묶음도 시트 밖(모듈)에 산다
  forgetSheetMemory();
  cleanup();
  ensureLocalStorage();
  window.localStorage.clear();
});
