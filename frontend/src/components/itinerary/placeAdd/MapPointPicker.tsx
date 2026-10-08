import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { appDataApi, useAsyncResource, type GeoRef, type ItineraryPlace, type LocateResult, type PlaceSearchItem, type TripAreaCenter } from "../../../api";
import { loadKakaoMaps, type KakaoMapsNamespace } from "../../../lib/kakaoMap";

export type MapPoint = { latitude: number; longitude: number };

/** 일정 지역도 공공데이터 장소도 가릴 수 없을 때 여는 자리 - 대한민국 가운데 */
export const KOREA_CENTER: MapPoint = { latitude: 36.5, longitude: 127.8 };
const AREA_LEVEL = 6;
const COUNTRY_LEVEL = 13;
/** 결과 자리나 지도에서 찾기 결과로 옮겨 열 때 - 건물이 보일 만큼 가깝다 */
const CLOSE_LEVEL = 3;
/** 지도에서 찾기 - 두 글자부터, 입력이 멎고 300ms 뒤에 묻고, 결과는 네 곳까지 */
const SEARCH_MIN = 2;
const SEARCH_DEBOUNCE_MS = 300;
const SEARCH_MAX = 4;
const SEARCHING = "찾는 중…";
const NO_RESULT = "결과가 없어요";
/** 카카오 지도의 확대 수준 범위 - 1 이 가장 가깝고 14 가 가장 넓다 */
const MIN_LEVEL = 1;
const MAX_LEVEL = 14;
/** 방향키 한 번에 지도를 옮기는 화면 픽셀(양수 dx = 오른쪽, 양수 dy = 아래쪽) */
const KEY_PAN_PX = 60;
const PAN_KEYS: Record<string, [number, number]> = {
  ArrowLeft: [-KEY_PAN_PX, 0],
  ArrowRight: [KEY_PAN_PX, 0],
  ArrowUp: [0, -KEY_PAN_PX],
  ArrowDown: [0, KEY_PAN_PX],
};
/** 확대 · 축소 키 - 한 번에 한 단계(수준이 작을수록 가깝다). '=' 는 Shift 없이 누른 '+' 자리다 */
const ZOOM_KEYS: Record<string, number> = { "+": -1, "=": -1, "-": 1 };

type KakaoMap = InstanceType<KakaoMapsNamespace["maps"]["Map"]>;

/** 지도를 여는 자리 - 카카오 결과 자리(kakao)나 공공데이터 장소(public). 열기만 한다 */
export type PickerStart = { center: MapPoint; origin: "kakao" | "public" };

/** 찍은 자리를 담는 값 - 지번 주소와 참조, pin 이면 공공데이터 중심. 찍은 좌표는 들어 있지 않다 */
export type PickedSpot = { address: string; geoRef: GeoRef; latitude: number | null; longitude: number | null };

/* 계획 0.5 - 찍은 자리는 그 자리를 품은 건물 · 땅의 지번으로만 담는다(데브톡 151842 · 151916-4). 찍은 좌표는 여기서 버린다:
   건물이거나 땅 중심이 가까우면 공공데이터 중심까지, 넓은 땅이면 주소만, 지번이 없으면 null(이름만) */
export function spotFromLocate(located: LocateResult): PickedSpot | null {
  const fill = located.fill;
  if (!fill) return null;
  const pin = located.nearCenter;
  return { address: fill.address, geoRef: { kind: fill.kind, id: fill.id, pin }, latitude: pin ? fill.latitude : null, longitude: pin ? fill.longitude : null };
}

/* 지도가 처음 여는 자리. 일정 지역 중심 → 일정에 이미 담긴 공공데이터 장소 → 대한민국 가운데 순이다(start 가 없을 때).
   카카오 결과 자리 · 지도에서 찾기 결과 자리에서 열거나 옮길 수 있다 - 보여 주기만(151842-3). 담는 것은 spotFromLocate 가 정한 지번뿐 */
export function pickerStart(
  area: TripAreaCenter | null,
  fallback: MapPoint | null,
): { center: MapPoint; level: number } {
  if (area && typeof area.latitude === "number" && typeof area.longitude === "number") {
    return { center: { latitude: area.latitude, longitude: area.longitude }, level: AREA_LEVEL };
  }
  if (fallback) return { center: fallback, level: AREA_LEVEL };
  return { center: KOREA_CENTER, level: COUNTRY_LEVEL };
}

/** 일정에 이미 담긴 공공데이터 장소 중 첫 좌표(Day 순서) - 지역 중심을 못 받았을 때 대신 쓴다 */
export function firstPublicPlacePoint(days: Record<number, ItineraryPlace[]>): MapPoint | null {
  const dayNumbers = Object.keys(days)
    .map(Number)
    .filter((day) => Number.isFinite(day))
    .sort((a, b) => a - b);
  for (const day of dayNumbers) {
    for (const place of days[day] ?? []) {
      if (
        place.placeOrigin === "public" &&
        typeof place.latitude === "number" &&
        typeof place.longitude === "number"
      ) {
        return { latitude: place.latitude, longitude: place.longitude };
      }
    }
  }
  return null;
}

const round6 = (value: number) => Math.round(value * 1e6) / 1e6;

/** 십자선 밑의 자리 - 소수 여섯 자리까지만 남긴다 */
function centerOf(map: KakaoMap): MapPoint {
  const point = map.getCenter();
  return { latitude: round6(point.getLat()), longitude: round6(point.getLng()) };
}

/** 서버가 받는 나만의 장소 위치 범위(customPlace 의 위도 33 ~ 39, 경도 124 ~ 132)와 같다 */
function isInKorea(point: MapPoint): boolean {
  return point.latitude >= 33 && point.latitude <= 39 && point.longitude >= 124 && point.longitude <= 132;
}

/* 지도에서 위치 찍기(나만의 장소의 선택 사항). 십자선은 지도 가운데에 고정돼 있고 지도를 옮겨 맞춘다:
   끌기 · 누르기(누른 자리가 가운데로 온다) · 방향키(지도가 화면 픽셀만큼 옮겨 간다) · + · -(확대 · 축소). '이 위치로' 단추나 Enter 가 십자선 밑의 자리를 고른다.
   '이 위치로'는 십자선 밑의 좌표로 그 자리를 품은 건물 · 땅의 지번을 물어 onPick 에 지번만 넘긴다(찍은 좌표는 넘기지 않는다).
   지도 위 '지도에서 찾기'는 지도를 그 자리로 옮기기만 한다 - 이름 칸은 건드리지 않는다.
   마우스 없이도 쓸 수 있게 지도 칸이 초점을 받고 이름이 있다. 열리면 지도에 초점을 두어 바로 방향키를 쓴다.
   지도가 멈출 때마다 가운데를 상태 한 줄로 알린다 - 화면을 보지 못해도 어디를 고르는지 안다. 대한민국 밖은 고르지 않는다(서버도 받지 않는다) */
export function MapPointPicker({
  tripId,
  fallbackCenter = null,
  start = null,
  onPick,
  onCancel,
}: {
  tripId: string;
  fallbackCenter?: MapPoint | null;
  start?: PickerStart | null;
  onPick: (spot: PickedSpot | null) => void;
  onCancel: () => void;
}) {
  const { data: area, isLoading } = useAsyncResource(() => appDataApi.getTripAreaCenter(tripId), [tripId]);
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<KakaoMap | null>(null);
  // 지도가 마지막으로 멈춘 자리의 가운데 - 지도가 뜨기 전에는 null
  const [center, setCenterPoint] = useState<MapPoint | null>(null);
  const [failed, setFailed] = useState(false);
  const [asking, setAsking] = useState(false);   // 지번을 묻는 동안 '이 위치로'를 끈다
  const [locateFailed, setLocateFailed] = useState(false);
  const askRef = useRef(0);   // 물음 번호 - 올리면 그 전 물음의 늦은 답은 버려진다. 올리는 쪽이 asking 도 맡는다(pickCenter 는 true, 지도가 멈추면 false)
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PlaceSearchItem[]>([]);
  const [searchNote, setSearchNote] = useState("");   // 지도에서 찾기 알림 칸의 글 - 찾는 중 · 결과 없음 · 비어 있음
  const [moved, setMoved] = useState<string | null>(null);   // 지도에서 찾기로 옮겨 온 곳의 이름 - 상태 줄에만 보인다
  const helpId = useId();
  // 중심 요청이 실패해도(data 가 null) 지도는 연다 - start, fallbackCenter, 대한민국 가운데 순으로
  const opening = start ? { center: start.center, level: CLOSE_LEVEL } : pickerStart(area, fallbackCenter);
  const inside = center !== null && isInKorea(center);

  // 지도에서 찾기 - 앞 요청은 끊고, 좌표가 있는 결과만 네 곳까지. 보여 주기만 하고 아무데도 담지 않는다
  useEffect(() => {
    const text = query.trim();
    if (text.length < SEARCH_MIN) {
      setResults([]);
      setSearchNote("");
      return;
    }
    setSearchNote(SEARCHING);
    const control = new AbortController();
    const timer = window.setTimeout(() => {
      appDataApi.searchPlaces(text, { signal: control.signal }).then(
        (items) => {
          if (control.signal.aborted) return;
          const found = items.filter((item) => typeof item.latitude === "number" && typeof item.longitude === "number").slice(0, SEARCH_MAX);
          setResults(found);
          setSearchNote(found.length ? "" : NO_RESULT);
        },
        () => {
          if (control.signal.aborted) return;
          setResults([]);
          setSearchNote(NO_RESULT);
        },
      );
    }, SEARCH_DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      control.abort();
    };
  }, [query]);

  useEffect(() => {
    if (isLoading || failed || !canvasRef.current) return;
    let disposed = false;
    loadKakaoMaps()
      .then((kakao) => {
        const canvas = canvasRef.current;
        if (disposed || !canvas) return;
        const map = new kakao.maps.Map(canvas, {
          center: new kakao.maps.LatLng(opening.center.latitude, opening.center.longitude),
          level: opening.level,
        });
        mapRef.current = map;
        // 누른 자리가 십자선 밑(가운데)으로 온다 - 핀을 따로 꽂지 않는다
        kakao.maps.event.addListener(map, "click", (event) => map.setCenter(event.latLng));
        // 끌기 · 방향키 · 확대 · 축소가 끝나 지도가 멈추면 가운데를 다시 읽는다 - 알림과 '이 위치로' 켜기에 쓴다
        const readCenter = () => {
          if (disposed) return;
          askRef.current += 1;   // 묻는 중이던 물음의 늦은 답은 pickCenter 의 askRef 비교에서 버려진다
          setAsking(false);   // 여기서 안 풀면 무른 물음의 답이 asking 을 풀 길이 없어 '이 위치로'가 취소 전까지 꺼져 있다
          setCenterPoint(centerOf(map));
        };
        kakao.maps.event.addListener(map, "idle", readCenter);
        readCenter();
        // 방향키를 바로 쓰게 지도에 초점을 둔다. 그 사이 사용자가 다른 곳에 초점을 뒀으면 뺏지 않는다
        if (!document.activeElement || document.activeElement === document.body) canvas.focus();
      })
      .catch(() => {
        if (!disposed) setFailed(true);
      });
    return () => {
      disposed = true;
      mapRef.current = null;
    };
  }, [isLoading, opening.center.latitude, opening.center.longitude, opening.level]);

  /* 십자선 밑의 지번을 묻고 지번만 넘긴다. 찍은 좌표는 묻는 데만 쓰고 onPick 에 싣지 않는다 */
  const pickCenter = async () => {
    const map = mapRef.current;
    if (!map || asking) return;   // 묻는 동안은 단추처럼 Enter 도 받지 않는다
    // 멈추기 전(알림 전)에 눌러도 지금 가운데로 다시 본다 - 대한민국 밖은 고르지 않는다
    const point = centerOf(map);
    if (!isInKorea(point)) return;
    const ask = ++askRef.current;
    setAsking(true);
    setLocateFailed(false);
    let located: LocateResult;
    try {
      located = await appDataApi.locatePlace(point.latitude, point.longitude);
    } catch {
      if (askRef.current === ask) {
        setAsking(false);
        setLocateFailed(true);
      }
      return;
    }
    if (askRef.current !== ask) return;   // 지도가 멈추며 이미 무른 물음이다 - asking 은 그때 풀었다
    setAsking(false);
    const now = mapRef.current ? centerOf(mapRef.current) : null;
    if (!now || now.latitude !== point.latitude || now.longitude !== point.longitude) return;   // 묻는 동안 지도가 움직였다 - 다시 고르게 둔다
    onPick(spotFromLocate(located));
  };

  /* 지도에서 찾기 결과를 누르면 지도만 그 자리로 옮긴다 - 이름 칸에는 아무것도 하지 않고, 지번은 '이 위치로'에서 묻는다 */
  const moveTo = (item: PlaceSearchItem) => {
    const map = mapRef.current;
    const kakao = window.kakao;
    if (!map || !kakao || typeof item.latitude !== "number" || typeof item.longitude !== "number") return;
    map.setCenter(new kakao.maps.LatLng(item.latitude, item.longitude));
    map.setLevel(CLOSE_LEVEL);
    setMoved(item.name);
    setLocateFailed(false);
    setQuery("");
    canvasRef.current?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    // 브라우저 단축키(Alt+← 뒤로가기, Ctrl+- 화면 축소 등)는 건드리지 않는다
    if (event.altKey || event.ctrlKey || event.metaKey) return;
    const map = mapRef.current;
    const pan = PAN_KEYS[event.key];
    const zoom = ZOOM_KEYS[event.key];
    if (pan) {
      event.preventDefault();
      map?.panBy(pan[0], pan[1]);
    } else if (zoom) {
      event.preventDefault();
      if (!map) return;
      const level = Math.min(MAX_LEVEL, Math.max(MIN_LEVEL, map.getLevel() + zoom));
      if (level !== map.getLevel()) map.setLevel(level);
    } else if (event.key === "Enter") {
      event.preventDefault();
      pickCenter();
    }
  };

  return (
    <section aria-label="지도에서 위치 찍기" className="map-point-picker">
      {failed ? (
        <p className="form-error">지도를 불러오지 못했어요. 위치 없이 이름만 담을 수 있어요.</p>
      ) : isLoading ? (
        <p className="place-search-status" role="status">
          지도를 준비하는 중이에요.
        </p>
      ) : (
        <>
          {/* 시안 v64: 지도에서 찾기 - 결과를 누르면 지도만 옮긴다(보여 주기만) */}
          <div className="map-point-picker-search">
            <label className="field">
              지도에서 찾기
              <input
                autoComplete="off"
                name="map-point-search"
                onChange={(event) => setQuery(event.target.value)}
                onKeyDown={(event) => {
                  // 이 칸의 Enter 가 바깥 양식(나만의 장소)을 보내지 않게 한다. Esc 는 결과만 닫는다
                  if (event.key === "Enter") event.preventDefault();
                  else if (event.key === "Escape" && results.length) {
                    event.preventDefault();
                    setResults([]);
                  }
                }}
                value={query}
              />
            </label>
            {/* 알림 칸은 늘 있어야 글이 바뀔 때 화면 읽기 프로그램이 읽는다 - 비어 있으면 화면에서는 숨긴다 */}
            <p className={searchNote ? "place-search-status" : "sr-only"} role="status">
              {searchNote}
            </p>
            {results.length > 0 && (
              <ul aria-label="지도에서 찾기 결과" className="mpp-results">
                {results.map((item) => (
                  <li key={item.id}>
                    <button className="mpp-result" onClick={() => moveTo(item)} type="button">
                      <strong>{item.name}</strong>
                      {item.address && <small>{item.address}</small>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          {/* 시안 v59 */}
          <p className="map-point-picker-help" id={helpId}>
            지도를 끌거나 눌러서 십자선을 원하는 곳에 맞추세요. 키보드로는 방향키로 지도를 옮기고 + · - 로 확대 · 축소하고 Enter 로 고릅니다.
          </p>
          <div className="map-point-picker-map">
            <div
              aria-describedby={helpId}
              aria-label="위치 고르기 지도"
              className="map-point-picker-canvas"
              onKeyDown={handleKeyDown}
              ref={canvasRef}
              role="application"
              tabIndex={0}
            />
            {/* 시안 v59: 가운데에 고정된 십자선 - 지도가 움직이고 십자선은 그대로다 */}
            <span aria-hidden="true" className="map-point-picker-pin" />
          </div>
          {moved !== null && (
            <p className="mpp-moved" role="status">
              ‘{moved}’ 자리로 옮겼어요. 십자선을 정확한 자리에 맞추고 ‘이 위치로’를 누르세요.
            </p>
          )}
          {/* 시안 v59: 지도가 멈출 때마다 바뀌는 상태 한 줄 - 대한민국 안이면 화면에는 숨기고(화면 읽기 프로그램만 읽는다) 밖이면 보인다 */}
          <p className={center && !inside ? "form-error" : "sr-only"} role="status">
            {center === null
              ? ""
              : inside
                ? `지도 가운데 위도 ${center.latitude.toFixed(4)}, 경도 ${center.longitude.toFixed(4)}`
                : "대한민국 밖이에요. 대한민국 안으로 옮겨 주세요."}
          </p>
          {locateFailed && (
            <p className="form-error" role="alert">
              지번을 확인하지 못했어요. 다시 찍거나 취소하고 이름만 담아 주세요.
            </p>
          )}
        </>
      )}
      <div className="map-point-picker-actions">
        <button className="btn sm line" onClick={onCancel} type="button">
          취소
        </button>
        {/* 묻는 동안은 disabled 가 아니라 aria-disabled - disabled 로 끄면 눌렀던 단추의 초점이 body 로 떨어진다. 눌러도 pickCenter 가 받지 않는다 */}
        <button aria-disabled={asking || undefined} className="btn sm primary" disabled={!inside} onClick={pickCenter} type="button">
          이 위치로
        </button>
      </div>
    </section>
  );
}
