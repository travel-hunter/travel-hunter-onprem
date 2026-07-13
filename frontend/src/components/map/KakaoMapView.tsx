import { useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { hasKakaoMapKey, loadKakaoMaps, type KakaoMapsNamespace } from "../../lib/kakaoMap";

export type KakaoMapMarker = {
  id: string;
  label: string;
  subtitle?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  query?: string | null;
};

type ResolvedCoordinate = {
  latitude: number;
  longitude: number;
};

type KakaoMapObject = {
  setMap: (map: unknown | null) => void;
};

type KakaoCustomOverlay = KakaoMapObject & {
  setZIndex?: (zIndex: number) => void;
};

function isValidCoordinate(marker: KakaoMapMarker): marker is KakaoMapMarker & { latitude: number; longitude: number } {
  return (
    typeof marker.latitude === "number" &&
    Number.isFinite(marker.latitude) &&
    typeof marker.longitude === "number" &&
    Number.isFinite(marker.longitude)
  );
}

function coordinateFromKakaoResult(result: { x: string; y: string } | undefined): ResolvedCoordinate | null {
  if (!result) return null;
  const latitude = Number(result.y);
  const longitude = Number(result.x);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return { latitude, longitude };
}

function searchByAddress(kakao: KakaoMapsNamespace, query: string): Promise<ResolvedCoordinate | null> {
  const Geocoder = kakao.maps.services?.Geocoder;
  const okStatus = kakao.maps.services?.Status.OK;
  if (!Geocoder || !okStatus) return Promise.resolve(null);
  return new Promise((resolve) => {
    new Geocoder().addressSearch(query, (results, status) => {
      resolve(status === okStatus ? coordinateFromKakaoResult(results[0]) : null);
    });
  });
}

function searchByKeyword(kakao: KakaoMapsNamespace, query: string): Promise<ResolvedCoordinate | null> {
  const Places = kakao.maps.services?.Places;
  const okStatus = kakao.maps.services?.Status.OK;
  if (!Places || !okStatus) return Promise.resolve(null);
  return new Promise((resolve) => {
    new Places().keywordSearch(query, (results, status) => {
      resolve(status === okStatus ? coordinateFromKakaoResult(results[0]) : null);
    });
  });
}

async function resolveMarkerCoordinate(kakao: KakaoMapsNamespace, marker: KakaoMapMarker): Promise<ResolvedCoordinate | null> {
  const query = marker.query?.trim();
  if (!query) return null;
  return (await searchByAddress(kakao, query)) ?? (await searchByKeyword(kakao, query));
}

function createMarkerLabelContent({
  getSelectedMarkerId,
  index,
  isSelected,
  marker,
  selectMarker,
}: {
  getSelectedMarkerId: () => string | null;
  index: number;
  isSelected: boolean;
  marker: KakaoMapMarker;
  selectMarker: (id: string | null) => void;
}): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `kakao-map-place-label${isSelected ? " selected" : ""}`;
  button.setAttribute("aria-label", `${marker.label} 선택`);
  button.setAttribute("aria-pressed", String(isSelected));

  const number = document.createElement("span");
  number.className = "kakao-map-place-label-number";
  number.textContent = String(index + 1);

  const label = document.createElement("strong");
  label.textContent = marker.label;
  label.title = marker.label;

  button.append(number, label);
  button.addEventListener("click", () => {
    selectMarker(getSelectedMarkerId() === marker.id ? null : marker.id);
  });
  return button;
}

function updateMarkerLabelSelection(label: HTMLButtonElement, isSelected: boolean) {
  label.classList.toggle("selected", isSelected);
  label.setAttribute("aria-pressed", String(isSelected));
}

export function KakaoMapView({
  ariaLabel,
  fallback,
  markers,
  onSelectMarker,
  selectedMarkerId,
}: {
  ariaLabel: string;
  fallback: ReactNode;
  markers: KakaoMapMarker[];
  onSelectMarker: (id: string | null) => void;
  selectedMarkerId: string | null;
}) {
  const canvasRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<unknown>(null);
  const mapObjectsRef = useRef<KakaoMapObject[]>([]);
  const labelElementsRef = useRef<Record<string, HTMLButtonElement>>({});
  const labelOverlaysRef = useRef<Record<string, KakaoCustomOverlay>>({});
  const onSelectMarkerRef = useRef(onSelectMarker);
  const selectedMarkerIdRef = useRef(selectedMarkerId);
  const [canUseSdk, setCanUseSdk] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  const [resolvedCoordinates, setResolvedCoordinates] = useState<Record<string, ResolvedCoordinate>>({});
  const hasMapKey = hasKakaoMapKey();
  const searchableMarkers = useMemo(
    () => markers.filter((marker) => !isValidCoordinate(marker) && Boolean(marker.query?.trim()) && !resolvedCoordinates[marker.id]),
    [markers, resolvedCoordinates],
  );
  const searchableMarkerKey = searchableMarkers.map((marker) => `${marker.id}:${marker.query}`).join("|");
  const validMarkers = useMemo(
    () =>
      markers
        .map((marker) => {
          if (isValidCoordinate(marker)) return marker;
          const resolved = resolvedCoordinates[marker.id];
          return resolved ? { ...marker, ...resolved } : marker;
        })
        .filter(isValidCoordinate),
    [markers, resolvedCoordinates],
  );
  const validMarkerKey = validMarkers
    .map((marker) => `${marker.id}:${marker.label}:${marker.latitude}:${marker.longitude}`)
    .join("|");
  const canTryCoordinateResolution = hasMapKey && searchableMarkers.length > 0;
  const shouldUseFallback = loadFailed || !hasMapKey || validMarkers.length === 0;

  useEffect(() => {
    onSelectMarkerRef.current = onSelectMarker;
  }, [onSelectMarker]);

  useLayoutEffect(() => {
    selectedMarkerIdRef.current = selectedMarkerId;
    for (const [markerId, label] of Object.entries(labelElementsRef.current)) {
      const isSelected = selectedMarkerId === markerId;
      updateMarkerLabelSelection(label, isSelected);
      labelOverlaysRef.current[markerId]?.setZIndex?.(isSelected ? 20 : 10);
    }
  });

  useEffect(() => {
    if (!canTryCoordinateResolution) return;
    let disposed = false;
    loadKakaoMaps()
      .then(async (kakao) => {
        const results = await Promise.all(
          searchableMarkers.map(async (marker) => ({
            id: marker.id,
            coordinate: await resolveMarkerCoordinate(kakao, marker),
          })),
        );
        if (disposed) return;
        setResolvedCoordinates((previous) => {
          const next = { ...previous };
          for (const result of results) {
            if (result.coordinate) next[result.id] = result.coordinate;
          }
          return next;
        });
      })
      .catch(() => {
        if (!disposed) setLoadFailed(true);
      })
    return () => {
      disposed = true;
    };
  }, [canTryCoordinateResolution, searchableMarkerKey]);

  useEffect(() => {
    if (shouldUseFallback || validMarkers.length === 0 || !canvasRef.current) return;
    let disposed = false;

    loadKakaoMaps()
      .then((kakao) => {
        if (disposed || !canvasRef.current) return;
        const centerMarker = validMarkers[0];
        const center = new kakao.maps.LatLng(centerMarker.latitude, centerMarker.longitude);
        const map = new kakao.maps.Map(canvasRef.current, { center, level: validMarkers.length > 1 ? 8 : 5 });
        const bounds = new kakao.maps.LatLngBounds();
        mapObjectsRef.current.forEach((mapObject) => mapObject.setMap(null));
        labelElementsRef.current = {};
        labelOverlaysRef.current = {};
        const nextMapObjects = validMarkers.flatMap((marker, index) => {
          const position = new kakao.maps.LatLng(marker.latitude, marker.longitude);
          bounds.extend(position);
          const kakaoMarker = new kakao.maps.Marker({ map, position, title: marker.label });
          kakao.maps.event.addListener(kakaoMarker, "click", () => onSelectMarkerRef.current(marker.id));
          const labelContent = createMarkerLabelContent({
            getSelectedMarkerId: () => selectedMarkerIdRef.current,
            index,
            isSelected: selectedMarkerIdRef.current === marker.id,
            marker,
            selectMarker: (markerId) => onSelectMarkerRef.current(markerId),
          });
          const labelOverlay = new kakao.maps.CustomOverlay({
            clickable: true,
            content: labelContent,
            map,
            position,
            xAnchor: 0.5,
            yAnchor: 1.75,
            zIndex: selectedMarkerIdRef.current === marker.id ? 20 : 10,
          }) as KakaoCustomOverlay;
          labelElementsRef.current[marker.id] = labelContent;
          labelOverlaysRef.current[marker.id] = labelOverlay;
          return [kakaoMarker, labelOverlay];
        });

        if (validMarkers.length > 1) map.setBounds(bounds);
        else map.setCenter(center);
        mapObjectsRef.current = nextMapObjects;
        mapRef.current = map;
        setCanUseSdk(true);
      })
      .catch(() => {
        if (!disposed) setLoadFailed(true);
      });

    return () => {
      disposed = true;
      mapObjectsRef.current.forEach((mapObject) => mapObject.setMap(null));
      mapObjectsRef.current = [];
      labelElementsRef.current = {};
      labelOverlaysRef.current = {};
      mapRef.current = null;
    };
  }, [shouldUseFallback, validMarkerKey]);

  if (shouldUseFallback) {
    return (
      <section className="kakao-map-view" data-kakao-map-view role="region" aria-label={ariaLabel}>
        {fallback}
      </section>
    );
  }

  return (
    <section className="kakao-map-view" data-kakao-map-view role="region" aria-label={ariaLabel}>
      <div className="kakao-map-canvas" ref={canvasRef} aria-hidden={!canUseSdk} />
    </section>
  );
}
