import { useCallback, useEffect, useState } from "react";
import { appDataApi, type TravelAreaCatalog, type TravelAreaOption } from "../../api";

const SIDO_OPTIONS = [
  "서울",
  "부산",
  "대구",
  "인천",
  "광주",
  "대전",
  "울산",
  "세종",
  "경기",
  "강원",
  "충북",
  "충남",
  "전북",
  "전남",
  "경북",
  "경남",
  "제주",
] as const;

type TripRegionSelectorProps = {
  selectedSido: string | null;
  value: TravelAreaOption | null;
  onSidoChange: (sido: string) => void;
  onChange: (area: TravelAreaOption) => void;
  disabled?: boolean;
  error?: string;
  /* 기존 일정을 열 때 저장돼 있던 선택을 되살린다. 카탈로그가 도착해야 옵션 객체를
     만들 수 있으므로 복원은 여기서 한 번만 일어난다. */
  restoreAreaId?: string | null;
  restoreAreaName?: string | null;
  /* 복원은 사용자의 선택이 아니다. onChange 로 흘리면 "지역을 바꿨다"로 오해돼
     손대지 않은 일정의 지역이 저장 때 갈아치워진다. 그래서 통로를 나눈다. */
  onRestore?: (area: TravelAreaOption) => void;
  /* 생성 화면은 이모지가 붙은 자기 순서의 시도 목록을 쓴다. 없으면 기본 17개다. */
  sidoOptions?: readonly { value: string; label: string; emoji?: string }[];
  /* 카탈로그에 없는 동적 권역(정책 연계 `policy-region:`, 옛 도시 질의 결과)을 함께 보여준다. */
  extraAreas?: readonly TravelAreaOption[];
};

/** 저장된 ID -> 같은 이름 -> 광역 전체 순으로만 되살린다. 못 찾으면 아무것도 고르지 않는다. */
export function resolveRestoredArea(
  catalog: TravelAreaCatalog,
  areaId: string | null | undefined,
  areaName: string | null | undefined,
): TravelAreaOption | null {
  const every = [
    catalog.wholeArea,
    ...catalog.recommendedAreas,
    ...catalog.administrativeAreas,
  ];
  if (areaId) {
    const byId = every.find((area) => area.travelAreaId === areaId);
    if (byId) return byId;
  }
  if (areaName) {
    const byName = every.find((area) => area.travelAreaName === areaName);
    if (byName) return byName;
  }
  return catalog.wholeArea ?? null;
}

const SIDO_SET = new Set<string>(SIDO_OPTIONS);
const PREFIXED_AREA_ID = /^(?:whole|admin|policy-region):([^:]+)/;

/** 저장된 일정에서 광역시도를 추려낸다. ID 접두사가 가장 믿을 만하고, 그다음이 표시 이름이다. */
export function resolveTripSido(
  areaId: string | null | undefined,
  region: string | null | undefined,
): string | null {
  const prefixed = areaId ? PREFIXED_AREA_ID.exec(areaId) : null;
  if (prefixed) {
    const decoded = decodeURIComponent(prefixed[1]);
    if (SIDO_SET.has(decoded)) return decoded;
  }
  const trimmed = (region ?? "").trim();
  if (SIDO_SET.has(trimmed)) return trimmed;
  const head = trimmed.split(/\s+/)[0] ?? "";
  return SIDO_SET.has(head) ? head : null;
}

function areaButtonLabel(area: TravelAreaOption) {
  return [area.travelAreaName, area.includedCities.join(", ")].filter(Boolean).join(" ");
}

function AreaOptionButton({
  area,
  isSelected,
  disabled,
  onSelect,
}: {
  area: TravelAreaOption;
  isSelected: boolean;
  disabled?: boolean;
  onSelect: (area: TravelAreaOption) => void;
}) {
  return (
    <button
      type="button"
      className={isSelected ? "trip-region-selector__area is-selected" : "trip-region-selector__area"}
      aria-pressed={isSelected}
      aria-label={areaButtonLabel(area)}
      disabled={disabled}
      onClick={() => onSelect(area)}
    >
      <span className="trip-region-selector__area-name">{area.travelAreaName}</span>
      <span className="trip-region-selector__area-cities">{area.includedCities.join(", ")}</span>
    </button>
  );
}

function AreaGroup({
  legend,
  areas,
  selectedAreaId,
  disabled,
  onSelect,
}: {
  legend: string;
  areas: TravelAreaOption[];
  selectedAreaId: string | null;
  disabled?: boolean;
  onSelect: (area: TravelAreaOption) => void;
}) {
  if (areas.length === 0) return null;

  return (
    <fieldset className="trip-region-selector__group">
      <legend>{legend}</legend>
      <div className="trip-region-selector__area-list">
        {areas.map((area) => (
          <AreaOptionButton
            key={area.travelAreaId}
            area={area}
            isSelected={area.travelAreaId === selectedAreaId}
            disabled={disabled}
            onSelect={onSelect}
          />
        ))}
      </div>
    </fieldset>
  );
}

export function TripRegionSelector({
  selectedSido,
  value,
  onSidoChange,
  onChange,
  disabled = false,
  error,
  restoreAreaId,
  restoreAreaName,
  onRestore,
  sidoOptions,
  extraAreas,
}: TripRegionSelectorProps) {
  const [catalog, setCatalog] = useState<TravelAreaCatalog | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (!selectedSido) {
      setCatalog(null);
      setIsLoading(false);
      setLoadError("");
      return;
    }

    let isCurrent = true;
    setIsLoading(true);
    setLoadError("");

    appDataApi
      .getTravelAreaCatalog(selectedSido)
      .then((nextCatalog) => {
        if (!isCurrent) return;
        setCatalog(nextCatalog);
      })
      .catch(() => {
        if (!isCurrent) return;
        setLoadError("여행권역을 불러오지 못했습니다.");
      })
      .finally(() => {
        if (isCurrent) setIsLoading(false);
      });

    return () => {
      isCurrent = false;
    };
  }, [retryToken, selectedSido]);

  /* 카탈로그가 도착했는데 아직 고른 것이 없으면 저장돼 있던 선택을 되살린다.
     사용자가 이미 다른 것을 골랐다면 건드리지 않는다. */
  useEffect(() => {
    if (!catalog || catalog.sido !== selectedSido) return;
    if (value && value.sido === selectedSido) return;
    if (!restoreAreaId && !restoreAreaName) return;
    const restored = resolveRestoredArea(catalog, restoreAreaId, restoreAreaName);
    if (restored) (onRestore ?? onChange)(restored);
    // onChange 는 매 렌더 새로 만들어질 수 있어 의존성에서 뺀다. 복원은 카탈로그 기준이다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog, restoreAreaId, restoreAreaName, selectedSido, value]);

  const retry = useCallback(() => {
    setRetryToken((token) => token + 1);
  }, []);

  const sidoList: readonly { value: string; label: string; emoji?: string }[] =
    sidoOptions ?? SIDO_OPTIONS.map((sido) => ({ value: sido, label: sido }));
  /* 카탈로그와 동적 권역에는 같은 곳이 ID 만 다르게 들어올 수 있다.
     예: 카탈로그의 `whole:부산` 과 추천 API 의 `busan-all` 은 둘 다 "부산 전체"다.
     이름이 겹치면 하나만 남긴다. 지금 선택된 쪽이 있으면 그쪽을 남겨야
     선택 표시가 사라지지 않는다. 아니면 카탈로그를 남긴다. */
  const activeExtras = (extraAreas ?? []).filter(
    (area) => area.sido === selectedSido,
  );
  const selectedId = value?.sido === selectedSido ? value.travelAreaId : null;
  const catalogAll = (() => {
    const source = catalog?.sido === selectedSido ? catalog : null;
    if (!source) return [] as TravelAreaOption[];
    return [
      source.wholeArea,
      ...source.recommendedAreas,
      ...source.administrativeAreas,
    ];
  })();
  const catalogIds = new Set(catalogAll.map((area) => area.travelAreaId));
  const catalogNames = new Set(catalogAll.map((area) => area.travelAreaName));
  /* 선택된 동적 권역이 카탈로그의 같은 이름을 밀어낸다. */
  const shownExtras = activeExtras.filter(
    (area) =>
      !catalogIds.has(area.travelAreaId) &&
      (!catalogNames.has(area.travelAreaName) ||
        area.travelAreaId === selectedId),
  );
  const suppressedNames = new Set(
    shownExtras
      .filter((area) => catalogNames.has(area.travelAreaName))
      .map((area) => area.travelAreaName),
  );
  const withoutSuppressed = (areas: TravelAreaOption[]) =>
    areas.filter((area) => !suppressedNames.has(area.travelAreaName));

  const selectedAreaId = value?.sido === selectedSido ? value.travelAreaId : null;
  const currentValue = value?.sido === selectedSido ? value : null;
  const activeCatalog = catalog?.sido === selectedSido ? catalog : null;
  /* 카탈로그가 아직 없어도 동적 권역은 고를 수 있어야 한다. 정책 연계나 옛 도시 질의로
     들어온 경우 그 하나가 유일한 선택지일 수 있다. */
  const recommendedAreas = [
    ...withoutSuppressed(activeCatalog?.recommendedAreas ?? []),
    ...shownExtras,
  ];
  const hasAnyArea =
    Boolean(activeCatalog) || recommendedAreas.length > 0;

  return (
    <section className="trip-region-selector" aria-label="여행 지역 선택">
      <div className="trip-region-selector__sido-grid">
        {sidoList.map((sido) => (
          <button
            key={sido.value}
            type="button"
            className={sido.value === selectedSido ? "trip-region-selector__sido is-selected" : "trip-region-selector__sido"}
            aria-pressed={sido.value === selectedSido}
            disabled={disabled}
            onClick={() => onSidoChange(sido.value)}
          >
            {sido.emoji && <span aria-hidden="true">{sido.emoji}</span>}
            <strong>{sido.label}</strong>
          </button>
        ))}
      </div>

      {error && <p className="trip-region-selector__error">{error}</p>}
      {isLoading && <p className="trip-region-selector__status">여행권역을 불러오는 중입니다.</p>}
      {loadError && (
        <div className="trip-region-selector__error-panel" role="alert">
          <span>{loadError}</span>
          <button type="button" onClick={retry} disabled={disabled || isLoading}>
            다시 시도
          </button>
        </div>
      )}

      {hasAnyArea ? (
        <div className="trip-region-selector__catalog">
          <h3 className="trip-region-selector__detail-heading">
            {selectedSido ? `${selectedSido} 세부 지역 선택` : "세부 지역 선택"}
          </h3>
          {activeCatalog && (
            <AreaGroup
              legend="전체"
              areas={withoutSuppressed([activeCatalog.wholeArea])}
              selectedAreaId={selectedAreaId}
              disabled={disabled}
              onSelect={onChange}
            />
          )}
          <AreaGroup
            legend="추천 여행권역"
            areas={recommendedAreas}
            selectedAreaId={selectedAreaId}
            disabled={disabled}
            onSelect={onChange}
          />
          {activeCatalog && (
            <AreaGroup
              legend="시·군·구"
              areas={withoutSuppressed(activeCatalog.administrativeAreas)}
              selectedAreaId={selectedAreaId}
              disabled={disabled}
              onSelect={onChange}
            />
          )}
        </div>
      ) : currentValue ? (
        <fieldset className="trip-region-selector__group">
          <legend>현재 선택</legend>
          <div className="trip-region-selector__area-list">
            <AreaOptionButton area={currentValue} isSelected disabled={disabled} onSelect={onChange} />
          </div>
        </fieldset>
      ) : null}
    </section>
  );
}

export type { TripRegionSelectorProps };
export { SIDO_OPTIONS as tripRegionSidoOptions };
