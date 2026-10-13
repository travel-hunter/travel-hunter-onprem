import { useCallback, useEffect, useRef, useState } from "react";
import { appDataApi, type PlaceMatchResult, type PlaceSearchCandidate, type PublicPlaceItem } from "../../../api";
import type { CustomPlaceReason, CustomStart } from "./CustomPlaceForm";
import type { MapPoint } from "./MapPointPicker";
import { publicBasketItem, type PlaceBasketItem } from "./placeBasket";

/* 고른 카카오 장소를 공공데이터와 맞춰 본 결과의 상태.
   choose = '이 장소가 맞나요?' 후보 1~3곳(fallback = '아니요' 를 누르면 여는 칸의 시작값), custom = 나만의 장소 칸(reason 은 왜 열렸는지, start 는 칸의 시작값).
   pickId = 칸을 열 때마다 달라지는 번호 - 화면이 이 번호로 칸을 새로 그려, 앞 장소에 적던 이름이 새로 고른 카카오 ID 에 붙지 않는다.
   카카오 이름 · 주소는 상태에 두지 않는다 - 이름은 사용자가 친 검색어(typedName)뿐이고, 남는 카카오 값은 장소 ID 숫자와
   지도를 여는 데만 쓰는 좌표(openAt)다. openAt 은 보여 주기만 하고 저장하지 않는다(151842-3) */
export type PlaceMatchState =
  | { status: "idle" }
  | { status: "matching" }
  | { status: "choose"; kakaoPlaceId: string | null; candidates: PublicPlaceItem[]; fallback: CustomStart }
  | { status: "custom"; kakaoPlaceId: string | null; reason: CustomPlaceReason; pickId: number; start: CustomStart };

/* pick 이 읽는 카카오 값은 이 다섯 칸뿐이다(+ 서버가 미리 맞춘 publicMatch - 공공데이터 값, 검색 후보에만 있다). 검색 후보(PlaceSearchCandidate)가 그대로 맞고,
   홈 넘김은 PlaceSearchItem 에서 { id, title: name, latitude, longitude, categoryCode } 를 만들어 넘긴다(publicMatch 없음 → 서버에 묻는다) */
export type PlacePickInput = Pick<PlaceSearchCandidate, "id" | "title" | "latitude" | "longitude" | "categoryCode"> & {
  publicMatch?: PlaceMatchResult | null;
};

const IDLE: PlaceMatchState = { status: "idle" };
const EMPTY_START: CustomStart = { typedName: "", fill: null, openAt: null };
const KAKAO_ID = /^kakao:(\d{1,20})$/;

/** 후보 id `kakao:{숫자}` 에서 숫자만. 모양이 다르면 null (externalPlaceId 로 돌아가지 않는다) */
export function kakaoPlaceIdOf(candidate: Pick<PlaceSearchCandidate, "id">): string | null {
  return KAKAO_ID.exec(candidate.id ?? "")?.[1] ?? null;
}

const pointOf = (candidate: PlacePickInput): MapPoint | null =>
  typeof candidate.latitude === "number" && typeof candidate.longitude === "number" && Number.isFinite(candidate.latitude) && Number.isFinite(candidate.longitude)
    ? { latitude: candidate.latitude, longitude: candidate.longitude }
    : null;

export function usePlaceMatch({ onMatched }: { onMatched: (item: PlaceBasketItem) => void }) {
  const [state, setState] = useState<PlaceMatchState>(IDLE);
  const stateRef = useRef<PlaceMatchState>(IDLE);
  const onMatchedRef = useRef(onMatched);
  // 새로 고르거나 닫을 때마다 올린다 - 늦게 도착한 앞 요청의 답을 걸러 낸다
  const turnRef = useRef(0);

  useEffect(() => {
    onMatchedRef.current = onMatched;
  }, [onMatched]);

  useEffect(
    () => () => {
      turnRef.current += 1;
    },
    [],
  );

  const commit = useCallback((next: PlaceMatchState) => {
    stateRef.current = next;
    setState(next);
  }, []);

  const reset = useCallback(() => {
    turnRef.current += 1;
    commit(IDLE);
  }, [commit]);

  /* 맞춰 본 답(서버가 미리 준 것이든 고른 뒤 물은 것이든)을 상태로 옮긴다. 시안 v64: 없으면 지번(fill)으로 주소 채움, 지번도 없으면 그 자리에서 위치 찍기 */
  const settle = useCallback(
    (answer: PlaceMatchResult, kakaoPlaceId: string | null, turn: number, typedName: string, openAt: MapPoint | null) => {
      const [first] = answer.places;
      const start: CustomStart = { typedName, fill: answer.fill ?? null, openAt };
      if (answer.result === "match" && first) {
        commit(IDLE);
        onMatchedRef.current(publicBasketItem(first, kakaoPlaceId));
      } else if (answer.result === "candidates" && answer.places.length > 0) {
        commit({ status: "choose", kakaoPlaceId, candidates: answer.places.slice(0, 3), fallback: start });
      } else {
        commit({ status: "custom", kakaoPlaceId, reason: start.fill ? start.fill.kind : "pin", pickId: turn, start });
      }
    },
    [commit],
  );

  const pick = useCallback(
    async (candidate: PlacePickInput, typedQuery = ""): Promise<void> => {
      const turn = ++turnRef.current;
      const kakaoPlaceId = kakaoPlaceIdOf(candidate);
      const typedName = typedQuery.trim();
      const openAt = pointOf(candidate);
      if (candidate.publicMatch) {
        // 결정 24: 검색 응답에 미리 맞춘 갈래가 있으면 '맞춰 보는 중' 없이 바로 간다
        settle(candidate.publicMatch, kakaoPlaceId, turn, typedName, openAt);
        return;
      }
      if (!openAt) {
        commit({ status: "custom", kakaoPlaceId, reason: "noCoords", pickId: turn, start: { typedName, fill: null, openAt: null } });
        return;
      }
      commit({ status: "matching" });
      let answer: PlaceMatchResult;
      try {
        answer = await appDataApi.matchPlace({
          name: candidate.title,
          latitude: openAt.latitude,
          longitude: openAt.longitude,
          categoryCode: candidate.categoryCode ?? null,
        });
      } catch {
        // 실패한 줄은 지도를 결과 자리에서 열지 않는다
        if (turnRef.current === turn) commit({ status: "custom", kakaoPlaceId, reason: "failed", pickId: turn, start: { typedName, fill: null, openAt: null } });
        return;
      }
      if (turnRef.current !== turn) return;
      settle(answer, kakaoPlaceId, turn, typedName, openAt);
    },
    [commit, settle],
  );

  const chooseCandidate = useCallback(
    (place: PublicPlaceItem) => {
      const current = stateRef.current;
      if (current.status !== "choose") return;
      turnRef.current += 1;
      commit(IDLE);
      onMatchedRef.current(publicBasketItem(place, current.kakaoPlaceId));
    },
    [commit],
  );

  const chooseCustom = useCallback(() => {
    const current = stateRef.current;
    if (current.status !== "choose") return;
    turnRef.current += 1;
    commit({ status: "custom", kakaoPlaceId: current.kakaoPlaceId, reason: current.fallback.fill ? current.fallback.fill.kind : "pin", pickId: turnRef.current, start: current.fallback });
  }, [commit]);

  const startDirect = useCallback(
    (typedQuery = "") => {
      turnRef.current += 1;
      commit({ status: "custom", kakaoPlaceId: null, reason: "direct", pickId: turnRef.current, start: { ...EMPTY_START, typedName: typedQuery.trim() } });
    },
    [commit],
  );

  return { state, pick, chooseCandidate, chooseCustom, startDirect, reset };
}
