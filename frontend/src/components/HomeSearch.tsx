import { ChevronLeft, MapPin, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { appDataApi, type PlaceSearchItem, type Policy } from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { tripStatus } from "../utils";
import { readPlaceParam, writePlaceParam } from "../utils/placeHandoff";
import { NATIONWIDE_REGION } from "../utils/policyPrograms";
import { KakaoMapView } from "./map/KakaoMapView";
import { geoToMap, nearTarget } from "./map/nearby";
import { readBrowseState, searchBrowse, writeBrowseState, type BrowseState } from "./map/policyBrowse";
import { matchesPolicySearch, setPolicyConditions, usePolicyConditions } from "./map/policyConditions";
import { PolicySearchRows } from "./map/PolicyMapPanels";
import { useBrowseHistory } from "./map/useBrowseHistory";
import "../styles/policy-map.css";

/* 홈 통합 검색(시안 v56 · v57). 검색창은 모양 그대로 입력이 되고 그 아래 자리가 결과로 바뀐다 - 다른 화면으로 가지 않는다.
   찾을 말(q)과 연 장소 카드(pl)는 주소에 둬 정책 탭 · 일정에 다녀와도 뒤로 한 번에 그대로 돌아온다.
   층: 검색(q) → 장소 카드(pl). 치는 동안은 같은 층이라 기록이 쌓이지 않는다. */
const EXAMPLES = ["여수", "오동도", "해운대", "전주 한옥마을", "강릉 카페"];
const MIN_PLACE_QUERY = 2;
const PLACE_DEBOUNCE_MS = 300;

const homeDepthOf = (params: URLSearchParams) => (params.has("q") ? 1 : 0) + (params.get("pl") ? 1 : 0);
const lastCategory = (category: string | null | undefined) => (category ?? "").split(" > ").pop() || "장소";
const shortAddress = (address: string | null | undefined) => (address ?? "").split(/\s+/).slice(1, 3).join(" ");
const xyOf = (item: PlaceSearchItem) =>
  item.sido && item.latitude != null && item.longitude != null ? geoToMap(item.sido, item.latitude, item.longitude) : null;

/** 정책 탭 주소 - 기본값 · 예전 키 지우기는 writeBrowseState 한 곳에서 */
function policiesUrl(patch: Partial<BrowseState>) {
  const params = writeBrowseState(new URLSearchParams(), { ...readBrowseState(new URLSearchParams()), ...patch });
  const search = params.toString();
  return search ? `/policies?${search}` : "/policies";
}

export function useHomeSearchOpen() {
  const [searchParams] = useSearchParams();
  return searchParams.has("q");
}

export function HomeSearch({ policies, avatarLabel }: { policies: Policy[] | null; avatarLabel: string }) {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { go, back } = useBrowseHistory(homeDepthOf);
  const conditions = usePolicyConditions();
  const q = searchParams.get("q");
  const open = q !== null;
  const place = readPlaceParam(searchParams.get("pl"));
  /* 입력값은 이 칸이 쥔다 - 주소를 거쳐 되돌아오는 값을 입력칸에 그대로 넣으면 한글 조합이 끊긴다.
     주소가 밖에서 바뀌었을 때(뒤로 등)만 따라간다 */
  const [text, setText] = useState(q ?? "");
  const writtenRef = useRef(q);
  useEffect(() => {
    if (q === writtenRef.current) return;
    writtenRef.current = q;
    setText(q ?? "");
  }, [q]);
  const withParams = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null) next.delete(key);
      else next.set(key, value);
    }
    return next;
  };
  const typeText = (value: string) => {
    setText(value);
    writtenRef.current = value;
    go(withParams({ q: value, pl: null }));
  };
  const close = () => back(withParams({ q: null, pl: null }));
  const closePlace = () => back(withParams({ pl: null }));

  /* 장소(카카오)는 지역 · 혜택 이름이 맞아도 늘 묻는다 - 홈은 '여수'를 쳐도 여수의 장소 목록이 나와야 한다(정책 탭과 다르다) */
  const placeQuery = open ? text.trim() : "";
  const [places, setPlaces] = useState<PlaceSearchItem[] | null>(null);
  useEffect(() => {
    setPlaces(null);
    if (placeQuery.length < MIN_PLACE_QUERY) return;
    const control = new AbortController();
    const timer = window.setTimeout(() => {
      appDataApi.searchPlaces(placeQuery, { signal: control.signal }).then(
        (items) => setPlaces(items.filter((item) => item.kind === "place")),
        () => {
          if (!control.signal.aborted) setPlaces([]);
        },
      );
    }, PLACE_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      control.abort();
    };
  }, [placeQuery]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || document.querySelector('[role="dialog"][aria-modal="true"]')) return;
      if (place) closePlace();
      else close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  const query = text.trim();
  const all = policies ?? [];
  const found = query ? searchBrowse(all, query) : null;
  const fullTextCount = useMemo(() => (query ? all.filter((policy) => matchesPolicySearch(policy, query)).length : 0), [all, query]);
  const hasPolicyRows = Boolean(found && (found.regions.length || found.places.length || found.programs.length || fullTextCount));
  const loadingPlaces = query.length >= MIN_PLACE_QUERY && places === null;

  return (
    <>
      <div className="prototype-home-search-row">
        <label className={open ? "prototype-home-search-pill home-search-pill searching" : "prototype-home-search-pill home-search-pill"}>
          <Search size={15} aria-hidden="true" />
          <input
            id="home-search"
            type="search"
            aria-label="지역 · 혜택 · 장소 검색"
            aria-controls={open ? "home-search-results" : undefined}
            aria-expanded={open}
            autoComplete="off"
            enterKeyHint="search"
            placeholder="어디로 떠나세요?"
            value={text}
            onFocus={() => {
              if (!open) go(withParams({ q: "" }));
            }}
            onChange={(event) => typeText(event.target.value)}
          />
        </label>
        <Link className="prototype-home-avatar" to="/mypage" aria-label="마이페이지">
          {avatarLabel}
        </Link>
      </div>
      {open && (
        <div className="home-search-results" id="home-search-results" role="region" aria-label="검색 결과">
          <div className="home-search-head">
            <button className="home-search-back" type="button" aria-label={place ? "검색 결과로" : "검색 닫기"} onClick={place ? closePlace : close}>
              <ChevronLeft size={22} aria-hidden="true" />
            </button>
            <b>{place ? "장소" : "검색"}</b>
          </div>
          {place ? (
            <HomePlaceCard item={place} policies={all} onBack={closePlace} />
          ) : !query ? (
            <div className="home-search-start">
              <h3>이렇게 찾아 보세요</h3>
              <div className="home-search-examples">
                {EXAMPLES.map((example) => (
                  <button key={example} type="button" onClick={() => typeText(example)}>
                    {example}
                  </button>
                ))}
              </div>
              <p>지역이나 혜택 이름은 정책 탭으로, 장소는 카드로 열려요. 장소 카드에서 그 근처 혜택을 보거나 일정에 담을 수 있어요.</p>
            </div>
          ) : (
            <div className="home-search-body">
              {found && hasPolicyRows && (
                <PolicySearchRows
                  found={found}
                  query={query}
                  fullTextCount={fullTextCount}
                  onPickRegion={(region) => navigate(policiesUrl({ region }))}
                  onPickPlace={(region, city) => navigate(policiesUrl({ region, city }))}
                  onPickProgram={(program) => navigate(policiesUrl({ program }))}
                  onShowAll={() => {
                    setPolicyConditions({ ...conditions, text: query });
                    navigate("/policies");
                  }}
                />
              )}
              {places && places.length > 0 && (
                <>
                  <h3>장소<span className="src">카카오 지도</span></h3>
                  {places.map((item) => (
                    <HomePlaceRow key={item.id} item={item} policies={all} onOpen={() => go(withParams({ pl: writePlaceParam(item) }))} />
                  ))}
                </>
              )}
              {loadingPlaces && <p className="thmap-sres-empty">장소를 찾는 중…</p>}
              {!loadingPlaces && !hasPolicyRows && !places?.length && <p className="thmap-sres-empty">‘{query}’에 맞는 지역 · 혜택 · 장소가 없어요.</p>}
            </div>
          )}
        </div>
      )}
    </>
  );
}

function HomePlaceRow({ item, policies, onOpen }: { item: PlaceSearchItem; policies: Policy[]; onOpen: () => void }) {
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xyOf(item));
  const badge = target.region === NATIONWIDE_REGION ? null : target.note ? `근처 혜택 ${target.count}` : `혜택 ${target.count}`;
  return (
    <button className="thmap-sres-row home-place-row" type="button" onClick={onOpen}>
      <span className="thmap-near-ic" aria-hidden="true"><MapPin size={18} /></span>
      <span className="tx">
        <b>{item.name}</b>
        <span>{lastCategory(item.category)}{item.address ? ` · ${shortAddress(item.address)}` : ""}</span>
      </span>
      {badge && <span className="home-place-badge">{badge}</span>}
    </button>
  );
}

function HomePlaceCard({ item, policies, onBack }: { item: PlaceSearchItem; policies: Policy[]; onBack: () => void }) {
  const [picking, setPicking] = useState(false);
  const xy = xyOf(item);
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xy);
  /* 근처 혜택 = 정책 탭 위치로 찾기와 같은 화면(핀 · '근처' 줄 · 가까운 시군) */
  const nearUrl = policiesUrl({
    region: target.region,
    city: target.city,
    near: item.sido && item.latitude != null && item.longitude != null
      ? { name: item.name, lat: item.latitude, lng: item.longitude, sido: item.sido, region: target.region, city: target.city, note: target.note }
      : null,
  });
  return (
    <article className="home-place-card" aria-label={`${item.name} 장소 카드`}>
      <button className="home-place-back" type="button" onClick={onBack}>‹ 검색 결과</button>
      {item.category && <p className="home-place-cat">{item.category.split(" > ").join(" · ")}</p>}
      <h3>{item.name}</h3>
      {item.address && <p className="home-place-addr">{item.address}</p>}
      <div className="home-place-map">
        <KakaoMapView
          ariaLabel={`${item.name} 위치`}
          fallback={<div className="home-place-map-fallback"><MapPin size={18} aria-hidden="true" />{item.address ?? item.name}</div>}
          markers={[{ id: item.id, label: item.name, subtitle: lastCategory(item.category), latitude: item.latitude, longitude: item.longitude }]}
          onSelectMarker={() => undefined}
          selectedMarkerId={null}
        />
      </div>
      <div className="home-place-acts">
        <button className="home-place-primary" type="button" aria-expanded={picking} onClick={() => setPicking((value) => !value)}>
          일정에 담기
        </button>
        {target.note && <p className="home-place-note">{target.note}</p>}
        <Link className="home-place-near" to={nearUrl}>
          주변 혜택 {target.count}건 보기<span aria-hidden="true">›</span>
        </Link>
        {item.placeUrl && (
          <a className="home-place-kakao" href={item.placeUrl} target="_blank" rel="noopener noreferrer">
            카카오맵에서 자세히 ↗
          </a>
        )}
      </div>
      {picking && <TripPicker item={item} />}
    </article>
  );
}

/* 일정에 담기(시안 v57): 일정만 고른다. 고르면 그 일정 상세의 '장소 추가' 창이 이 장소를 바구니에 담은 채 열리고 날은 거기서 고른다.
   담을 곳은 끝나지 않은 일정 중 고칠 수 있는 것만(보기 권한이면 열자마자 막힌다) */
function TripPicker({ item }: { item: PlaceSearchItem }) {
  const navigate = useNavigate();
  const { data, error, isLoading } = useAsyncResource(() => appDataApi.listTrips(), []);
  const trips = (data ?? [])
    .filter((trip) => tripStatus(trip.startDate, trip.endDate)?.tone !== "past" && trip.currentUserRole !== "viewer")
    .sort((left, right) => left.startDate.localeCompare(right.startDate));
  const handoff = writePlaceParam(item);
  const newTripUrl = `/trips/new?${new URLSearchParams({ ...(item.sido ? { sido: item.sido } : {}), addPlace: handoff })}`;
  return (
    <div className="home-trip-pick" role="group" aria-label="일정 고르기">
      {isLoading ? (
        <p className="home-trip-pick-tip">일정을 불러오는 중…</p>
      ) : error ? (
        <p className="home-trip-pick-tip">일정 목록을 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>
      ) : trips.length > 0 ? (
        <>
          <h4>어느 일정에 담을까요?</h4>
          <p className="home-trip-pick-tip">고르면 그 일정의 장소 추가 창이 열려요. 날은 거기서 골라요.</p>
          {trips.map((trip) => (
            <button
              className="home-trip-pick-row"
              key={trip.id}
              type="button"
              onClick={() => navigate(`/trips/${trip.id}?${new URLSearchParams({ addPlace: handoff })}`)}
            >
              <b>{trip.title}</b>
              <span>{trip.dates}</span>
            </button>
          ))}
          <Link className="home-trip-pick-new" to={newTripUrl}>새 일정 만들기</Link>
        </>
      ) : (
        <>
          <h4>다가오는 일정이 없어요</h4>
          <p className="home-trip-pick-tip">일정을 만들면 그 일정의 장소 추가 창이 이 장소를 담은 채 열려요.</p>
          <Link className="home-place-primary" to={newTripUrl}>새 일정 만들기</Link>
        </>
      )}
    </div>
  );
}
