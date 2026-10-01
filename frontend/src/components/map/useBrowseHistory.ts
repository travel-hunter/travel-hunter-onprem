import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";

/* 주소를 화면 층에 맞춰 옮긴다. 층이 늘면 기록을 쌓고, 같으면 덮어쓰고, 줄면 쌓았던 기록을 되감는다.
   되감을 때 어디까지 쌓았는지는 기록마다 달아 둔 부모 주소 목록(thChain)이 안다 - 브라우저 기록은 앞뒤를
   들여다볼 수 없어서다. 그래서 기기·브라우저 뒤로가기와 화면 안 ‹ 가 쌓은 기록 위에서는 늘 같은 한 층을 걷는다.
   thLocal = 이 칸을 이 화면 안에서 고쳐 썼다는 표시. 없으면 앞 화면(홈 카드·일정)이 연 주소 그대로다. */
type BrowseHistoryState = { thChain?: string[]; thLocal?: boolean } | null;

const normalize = (search: string) => new URLSearchParams(search).toString();
const searchOf = (params: string) => (params ? `?${params}` : "");

export function useBrowseHistory(depthOf: (params: URLSearchParams) => number) {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as BrowseHistoryState;
  const chain = state?.thChain ?? [];
  /* 되감은 뒤 도착한 칸이 가려던 곳과 다르면(되감기는 한 번에 여러 층을 내릴 수 있다) 한 번 덮어쓴다 */
  const pendingRef = useRef<string | null>(null);

  useEffect(() => {
    const target = pendingRef.current;
    if (target === null) return;
    pendingRef.current = null;
    if (target !== normalize(location.search)) {
      navigate({ search: searchOf(target) }, { replace: true, state: { ...(location.state as object | null), thLocal: true } });
    }
  }, [location, navigate]);

  const replace = (target: string) => navigate({ search: searchOf(target) }, { replace: true, state: { ...state, thLocal: true } });

  const go = (next: URLSearchParams) => {
    const current = new URLSearchParams(location.search);
    const target = next.toString();
    if (target === current.toString()) return;
    const from = depthOf(current), to = depthOf(next);
    if (to > from) {
      navigate({ search: searchOf(target) }, { state: { thChain: [...chain, current.toString()], thLocal: true } });
      return;
    }
    if (to === from || chain.length === 0) {
      replace(target);
      return;
    }
    let steps = 0;
    for (let i = chain.length - 1; i >= 0; i -= 1) {
      steps += 1;
      if (depthOf(new URLSearchParams(chain[i])) <= to) break;
    }
    pendingRef.current = target;
    navigate(-steps);
  };

  /* 화면 안 ‹ · Esc - 늘 한 층만. 바로 아래 층이 쌓아 둔 기록 그대로면 브라우저 뒤로와 같고,
     같은 층끼리 덮어쓰며 부모가 한 층 넘게 아래가 됐으면(돋보기에서 시군을 고른 뒤 등) 한 층 아래로 덮어쓴다.
     앞 화면(홈 카드 등)이 이 층으로 바로 열었으면 뒤로 한 번에 그 화면으로. 주소로 바로 연 첫 칸이면 덮어쓴다. */
  const back = (lower: URLSearchParams | null) => {
    const target = lower?.toString() ?? null;
    if (chain.length > 0) {
      const parent = chain[chain.length - 1];
      if (target === null || parent === target) navigate(-1);
      /* 쌓은 뒤 같은 층에서 고친 것(위 칩 등)만 다르면 한 칸 되감고 고친 것을 얹는다 - 덮어쓰면 쌓아 둔 칸이
         남아 다음 뒤로가기가 옛 화면을 다시 연다 */
      else if (lower && depthOf(new URLSearchParams(parent)) === depthOf(lower)) {
        pendingRef.current = target;
        navigate(-1);
      } else replace(target);
    } else if (state?.thLocal || location.key === "default") {
      if (target !== null) replace(target);
    } else navigate(-1);
  };

  /* 층 밖 화면(필터 목록)으로 한 칸 - 지금 칸을 부모로 쌓아 기기 뒤로가기가 그 지도로 돌아온다 */
  const push = (next: URLSearchParams) => {
    const target = next.toString();
    if (target === normalize(location.search)) return;
    navigate({ search: searchOf(target) }, { state: { thChain: [...chain, normalize(location.search)], thLocal: true } });
  };

  /* 바로 아래 쌓아 둔 칸이 target 이면 되감고, 아니면 이 자리에서 바꾼다(필터 풀기 - 다른 화면으로는 나가지 않는다) */
  const unwind = (next: URLSearchParams) => {
    const target = next.toString();
    if (chain.length > 0 && chain[chain.length - 1] === target) navigate(-1);
    else replace(target);
  };

  return { go, back, push, unwind, replace };
}
