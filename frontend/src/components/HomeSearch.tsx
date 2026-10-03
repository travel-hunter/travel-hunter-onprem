import { ChevronLeft, MapPin, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { appDataApi, type NearbyCategory, type PlaceSearchItem, type Policy } from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { tripStatus } from "../utils";
import { readPlaceParam, writePlaceParam } from "../utils/placeHandoff";
import { cityOf, NATIONWIDE_REGION } from "../utils/policyPrograms";
import { KakaoMapView } from "./map/KakaoMapView";
import { geoToMap, nearTarget, policyCityFor, shortCity, type NearTarget } from "./map/nearby";
import { matchesBrowseFilter, readBrowseState, REGION_FULL_NAMES, searchBrowse, writeBrowseState, type BrowseState } from "./map/policyBrowse";
import { matchesPolicySearch, setPolicyConditions, usePolicyConditions } from "./map/policyConditions";
import { PolicySearchRows, SearchNoResults } from "./map/PolicyMapPanels";
import { useBrowseHistory } from "./map/useBrowseHistory";
import "../styles/policy-map.css";

/* 홈 통합 검색(시안 v56 · v57). 검색창은 모양 그대로 입력이 되고 그 아래 자리가 결과로 바뀐다 - 다른 화면으로 가지 않는다.
   찾을 말(q)과 연 장소 카드(pl)는 주소에 둬 정책 탭 · 일정에 다녀와도 뒤로 한 번에 그대로 돌아온다.
   층: 검색(q) → 장소 카드(pl) → 이 근처로 이어 본 장소 카드(lv 2, 3 …, 앞 장소 이름은 from). 치는 동안은 같은 층이라 기록이 쌓이지 않는다. */
const EXAMPLES = ["반값여행", "숙박세일", "여수", "오동도", "강릉 카페"];   // 혜택 이름도 - 무엇을 칠지 모를 때(10/3 사용자 조사)
const MIN_PLACE_QUERY = 2;
const PLACE_DEBOUNCE_MS = 300;

const placeLevelOf = (params: URLSearchParams) => (params.get("pl") ? Math.max(1, Number(params.get("lv")) || 1) : 0);
const homeDepthOf = (params: URLSearchParams) => (params.has("q") ? 1 : 0) + placeLevelOf(params);
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
    go(withParams({ q: value, pl: null, lv: null, from: null }));
  };
  const close = () => back(withParams({ q: null, pl: null, lv: null, from: null }));
  /* 이 근처로 이어 본 장소면 앞 장소로(쌓아 둔 기록 한 칸), 아니면 검색 결과로 */
  const level = placeLevelOf(searchParams);
  const toResults = () => withParams({ pl: null, lv: null, from: null });
  // 이어 본 장소면 앞 장소로 - 주소로 바로 열어 되감을 기록이 없으면 검색 결과로(10/3 리뷰)
  const closePlace = () => (level > 1 ? back(null, toResults()) : back(toResults()));
  const [nearCode, setNearCode] = useState<NearbyCategory>("FD6");
  /* 이 근처 결과 - 이 화면을 쓰는 동안 같은 장소 · 분류는 다시 묻지 않는다(앞 장소로 돌아올 때 바로 보인다) */
  const nearbyCache = useRef(new Map<string, PlaceSearchItem[]>()).current;

  /* 장소(카카오)는 지역 · 혜택 이름이 맞아도 늘 묻는다 - 홈은 '여수'를 쳐도 여수의 장소 목록이 나와야 한다(정책 탭과 다르다) */
  const placeQuery = open ? text.trim() : "";
  const [places, setPlaces] = useState<PlaceSearchItem[] | null>(null);
  /* 동 · 읍 · 면(같은 이름이 전국에 - '중앙동'). 정책 탭 위치로 찾기처럼 시군별로 보이고 그 근처 혜택으로 잇는다(10/3 사용자 조사) */
  const [areas, setAreas] = useState<PlaceSearchItem[]>([]);
  useEffect(() => {
    setPlaces(null);
    setAreas([]);
    if (placeQuery.length < MIN_PLACE_QUERY) return;
    const control = new AbortController();
    const timer = window.setTimeout(() => {
      appDataApi.searchPlaces(placeQuery, { signal: control.signal }).then(
        (items) => {
          setAreas(items.filter((item) => item.kind === "area"));
          setPlaces(items.filter((item) => item.kind === "place"));
        },
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
  /* 홈 건수는 정책 탭의 좁히기 조건(마감 · 금액 · 관심만)을 걸지 않은 전체로 센다 - 정책 탭으로 가면 조건 줄과 ✕ 가 함께 보인다 */
  const all = policies ?? [];
  const found = query ? searchBrowse(all, query) : null;
  const fullTextCount = useMemo(() => (query ? all.filter((policy) => matchesPolicySearch(policy, query)).length : 0), [all, query]);
  const hasPolicyRows = Boolean(found && (found.combos.length || found.regions.length || found.places.length || found.filters.length || found.programs.length || fullTextCount));
  /* 혜택 이름 · 형태를 친 말('반값' · '숙소')이면 상호명 장소(반값밧데리할인마트 …)는 접어 둔다 - 누르면 보인다(10/3 사용자 조사) */
  const benefitWords = Boolean(found && (found.combos.length || found.filters.length || found.programs.length));
  const [placesOpen, setPlacesOpen] = useState(false);
  useEffect(() => setPlacesOpen(false), [query]);
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
            onKeyDown={(event) => {
              // 검색 키(Enter) = 다 쳤다. 결과는 치는 대로 이미 보이니 초점만 빼 휴대폰 키보드를 내린다 - 결과를 가리지 않게.
              // 한글 조합을 끝내는 Enter 는 뺀다
              if (event.key === "Enter" && !event.nativeEvent.isComposing) event.currentTarget.blur();
            }}
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
            <HomePlaceCard
              key={place.id}
              item={place}
              policies={all}
              fromName={level > 1 ? searchParams.get("from") : null}
              nearCode={nearCode}
              nearbyCache={nearbyCache}
              onNearCode={setNearCode}
              onOpenNearby={(next) => go(withParams({ pl: writePlaceParam(next), lv: String(level + 1), from: place.name }))}
              onBack={closePlace}
            />
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
                  onPickCombo={(combo) => navigate(policiesUrl({ region: combo.region, city: combo.city, program: combo.program, filter: combo.filter }))}
                  onPickFilter={(filter) => navigate(policiesUrl({ filter }))}
                  onShowAll={() => {
                    setPolicyConditions({ ...conditions, text: query });
                    navigate("/policies");
                  }}
                />
              )}
              {areas.length > 0 && (
                <>
                  <h3>동네<span className="src">근처 혜택으로</span></h3>
                  {areas.map((item) => (
                    <HomeAreaRow key={item.id} item={item} policies={all} />
                  ))}
                </>
              )}
              {places && places.length > 0 && (benefitWords && !placesOpen ? (
                <button className="home-places-more" type="button" onClick={() => setPlacesOpen(true)}>
                  ‘{query}’ 이름이 든 장소도 보기 · {places.length}곳
                </button>
              ) : (
                <>
                  <h3>장소<span className="src">카카오 지도</span></h3>
                  {places.map((item) => (
                    <HomePlaceRow key={item.id} item={item} policies={all} onOpen={() => go(withParams({ pl: writePlaceParam(item), lv: null, from: null }))} />
                  ))}
                </>
              ))}
              {loadingPlaces && <p className="thmap-sres-empty">장소를 찾는 중…</p>}
              {!loadingPlaces && !hasPolicyRows && !places?.length && !areas.length && (
                <SearchNoResults
                  query={query}
                  policies={all}
                  onPickProgram={(program) => navigate(policiesUrl({ program }))}
                  onPickFilter={(filter) => navigate(policiesUrl({ filter }))}
                  onBrowseAll={() => navigate("/policies")}
                />
              )}
            </div>
          )}
        </div>
      )}
    </>
  );
}

/** 혜택이 있는 곳 이름 - 시군이면 '여수', 도 전체면 '전라남도' */
const targetPlaceName = (target: NearTarget) =>
  target.city ? shortCity(target.region, target.city) : REGION_FULL_NAMES[target.region] ?? target.region;

/** 근처 혜택 버튼 - 어느 시군 혜택인지, 넓혔으면 얼마나 먼지('주변 혜택 1건'이 45km 밖 시군이었다 - 10/3 사용자 조사) */
function nearLinkLabel(target: NearTarget) {
  if (target.region === NATIONWIDE_REGION) return `전국 공통 혜택 ${target.count}건 보기`;
  const where = targetPlaceName(target);
  return target.km != null ? `${where} 약 ${target.km}km · 혜택 ${target.count}건 보기` : `${where} 혜택 ${target.count}건 보기`;
}

/** 정책 탭의 그 근처 화면(위치로 찾기와 같은 핀 · '근처' 줄 · 가까운 시군) */
function nearUrlOf(item: PlaceSearchItem, target: NearTarget) {
  return policiesUrl({
    region: target.region,
    city: target.city,
    near: item.sido && item.latitude != null && item.longitude != null
      ? { name: item.name, lat: item.latitude, lng: item.longitude, sido: item.sido, region: target.region, city: target.city, note: target.note }
      : null,
  });
}

/* 동네 한 줄('여수시 중앙동') - 누르면 정책 탭의 그 근처 혜택 */
function HomeAreaRow({ item, policies }: { item: PlaceSearchItem; policies: Policy[] }) {
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xyOf(item));
  return (
    <Link className="thmap-sres-row home-area-row" to={nearUrlOf(item, target)}>
      <span className="thmap-near-ic" aria-hidden="true"><MapPin size={18} /></span>
      <span className="tx">
        <b>{item.name}</b>
        <span>
          <span className="thmap-near-to">→ {item.sido} {item.city}</span> ·{" "}
          {target.region === NATIONWIDE_REGION ? "전국 공통 혜택" : target.note ? "근처 혜택" : "혜택"} {target.count}건
        </span>
      </span>
    </Link>
  );
}

function HomePlaceRow({ item, policies, onOpen }: { item: PlaceSearchItem; policies: Policy[]; onOpen: () => void }) {
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xyOf(item));
  // 그 가게가 아니라 그 시군(도)의 혜택이라는 게 보이게 - '혜택 1'만 있으면 가게 할인처럼 읽혔다(10/3 사용자 조사)
  const badge = target.region === NATIONWIDE_REGION ? null : `${targetPlaceName(target)} 혜택 ${target.count}`;
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

function HomePlaceCard({
  item,
  policies,
  fromName,
  nearCode,
  nearbyCache,
  onNearCode,
  onOpenNearby,
  onBack,
}: {
  item: PlaceSearchItem;
  policies: Policy[];
  /** 이 근처로 이어 왔으면 앞 장소 이름 - '‹ 오동도' */
  fromName: string | null;
  nearCode: NearbyCategory;
  nearbyCache: Map<string, PlaceSearchItem[]>;
  onNearCode: (code: NearbyCategory) => void;
  onOpenNearby: (item: PlaceSearchItem) => void;
  onBack: () => void;
}) {
  const [picking, setPicking] = useState(false);
  const xy = xyOf(item);
  const target = nearTarget(policies, item.sido ?? null, item.city ?? null, xy);
  /* 근처 혜택 = 정책 탭 위치로 찾기와 같은 화면(핀 · '근처' 줄 · 가까운 시군) */
  const nearUrl = nearUrlOf(item, target);
  return (
    <article className="home-place-card" aria-label={`${item.name} 장소 카드`}>
      <button className="home-place-back" type="button" onClick={onBack}>‹ {fromName ?? "검색 결과"}</button>
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
          {nearLinkLabel(target)}<span aria-hidden="true">›</span>
        </Link>
        {item.placeUrl && (
          <a className="home-place-kakao" href={item.placeUrl} target="_blank" rel="noopener noreferrer">
            카카오맵에서 자세히 ↗
          </a>
        )}
      </div>
      {picking && <TripPicker item={item} />}
      <NearbySection item={item} policies={policies} code={nearCode} cache={nearbyCache} onCode={onNearCode} onOpen={onOpenNearby} />
    </article>
  );
}

/* 이 근처(시안 v58): 카카오 분류 반경 검색 - 맛집 · 카페 · 숙소 · 볼거리, 반경 2km 가까운 순 다섯 곳. 카카오는 별점 · 리뷰 ·
   인기 지표를 주지 않아 '인기순'이 아니다. 한 곳을 누르면 그 장소 카드로 이어 본다(뒤로 = 앞 장소). 같은 장소 · 분류는 다시 묻지 않는다 */
const NEARBY_TABS: readonly (readonly [NearbyCategory, string])[] = [["FD6", "맛집"], ["CE7", "카페"], ["AD5", "숙소"], ["AT4", "볼거리"]];
const NEARBY_SHOWN = 5;
const formatDistance = (meters: number) => (meters < 1000 ? `약 ${Math.max(10, Math.round(meters / 10) * 10)}m` : `약 ${(meters / 1000).toFixed(1)}km`);

/** 숙소 칸: 그 시군(없으면 도)의 숙박 혜택 건수 - 숙소마다 쓸 수 있는지는 혜택 조건에 달렸다 */
function stayBenefitNote(policies: Policy[], item: PlaceSearchItem) {
  if (!item.sido) return null;
  const stays = policies.filter((policy) => policy.region === item.sido && matchesBrowseFilter(policy, "stay"));
  const city = policyCityFor(policies, item.sido, item.city ?? null);
  const inCity = city ? stays.filter((policy) => cityOf(policy) === city).length : 0;
  const where = inCity && city ? shortCity(item.sido, city) : REGION_FULL_NAMES[item.sido] ?? item.sido;
  const count = inCity || stays.length;
  return count ? `${where} 숙박 혜택 ${count}건 - 숙소마다 쓸 수 있는지는 혜택 조건에서 확인해요` : null;
}

function NearbySection({
  item,
  policies,
  code,
  cache: nearbyCache,
  onCode,
  onOpen,
}: {
  item: PlaceSearchItem;
  policies: Policy[];
  code: NearbyCategory;
  cache: Map<string, PlaceSearchItem[]>;
  onCode: (code: NearbyCategory) => void;
  onOpen: (item: PlaceSearchItem) => void;
}) {
  const key = `${item.id}|${code}`;
  const [result, setResult] = useState<{ key: string; items: PlaceSearchItem[] | null; failed: boolean }>({ key, items: nearbyCache.get(key) ?? null, failed: false });
  useEffect(() => {
    const cached = nearbyCache.get(key);
    if (cached) {
      setResult({ key, items: cached, failed: false });
      return;
    }
    setResult({ key, items: null, failed: false });
    if (item.latitude == null || item.longitude == null) {
      setResult({ key, items: [], failed: false });
      return;
    }
    const control = new AbortController();
    appDataApi.listNearbyPlaces(item.latitude, item.longitude, code, { signal: control.signal }).then(
      (list) => {
        const shown = list.filter((place) => place.id !== item.id).slice(0, NEARBY_SHOWN);
        nearbyCache.set(key, shown);
        setResult({ key, items: shown, failed: false });
      },
      () => {
        if (!control.signal.aborted) setResult({ key, items: [], failed: true });
      },
    );
    return () => control.abort();
  }, [key]);
  const items = result.key === key ? result.items : null;
  const note = code === "AD5" ? stayBenefitNote(policies, item) : null;
  return (
    <section className="home-nearby" aria-label="이 근처">
      <h4>
        이 근처<span className="src">반경 2km · 가까운 순</span>
      </h4>
      <div className="home-nearby-tabs" role="group" aria-label="이 근처 종류">
        {NEARBY_TABS.map(([value, label]) => (
          <button key={value} type="button" aria-pressed={value === code} onClick={() => onCode(value)}>
            {label}
          </button>
        ))}
      </div>
      {note && <p className="home-nearby-stay">{note}</p>}
      {items === null ? (
        <p className="home-trip-pick-tip">근처를 찾는 중…</p>
      ) : result.failed ? (
        <p className="home-trip-pick-tip">근처 장소를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.</p>
      ) : items.length === 0 ? (
        <p className="home-trip-pick-tip">반경 2km 안에 없어요.</p>
      ) : (
        items.map((place) => (
          <button className="thmap-sres-row home-nearby-row" key={place.id} type="button" onClick={() => onOpen(place)}>
            <span className="tx">
              <b>{place.name}</b>
              <span>
                {lastCategory(place.category)}
                {place.distanceMeters != null ? ` · ${formatDistance(place.distanceMeters)}` : ""}
              </span>
            </span>
            <span className="go" aria-hidden="true">›</span>
          </button>
        ))
      )}
    </section>
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
