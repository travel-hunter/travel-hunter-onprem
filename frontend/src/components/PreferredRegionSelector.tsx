import { useMemo, useState } from "react";
import { getRegionIcon } from "./preferenceDisplay";

export function PreferredRegionSelector({
  compact = false,
  disabled = false,
  maxSelections = 3,
  onChange,
  options,
  value,
}: {
  compact?: boolean;
  disabled?: boolean;
  maxSelections?: number;
  onChange: (regions: string[]) => void;
  options: readonly string[];
  value: readonly string[];
}) {
  const [query, setQuery] = useState("");
  const selected = value.filter((region) => options.includes(region)).slice(0, maxSelections);
  const selectedSet = useMemo(() => new Set(selected), [selected]);
  const normalizedQuery = query.trim();
  const visibleOptions = normalizedQuery ? options.filter((region) => region.includes(normalizedQuery)) : options;
  const isAtLimit = selected.length >= maxSelections;

  const toggle = (region: string) => {
    if (disabled) return;
    if (selectedSet.has(region)) {
      onChange(selected.filter((item) => item !== region));
      return;
    }
    if (isAtLimit) return;
    onChange([...selected, region]);
  };

  const selectedLabel = selected.length > 0 ? selected.join(" · ") : "아직 선택한 지역이 없어요.";

  return (
    <div className={compact ? "preferred-region-selector compact" : "preferred-region-selector"}>
      <div className="preferred-region-selector-head">
        <label className="field compact">
          <span>지역 검색</span>
          <input
            disabled={disabled}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="17개 광역시도 검색"
            type="search"
            value={query}
          />
        </label>
        <span className={isAtLimit ? "meta preferred-region-count active" : "meta preferred-region-count"}>{selected.length}/{maxSelections} 선택</span>
      </div>
      <div className="preferred-region-selected-summary" aria-live="polite">
        <span>선택된 관심지역</span>
        <strong>{selectedLabel}</strong>
      </div>
      <div className="choice-grid preferred-region-grid" aria-label="관심 지역 선택">
        {visibleOptions.map((region) => {
          const active = selectedSet.has(region);
          const blocked = !active && isAtLimit;
          return (
            <button
              aria-pressed={active}
              className={active ? "preferred-region-card active" : "preferred-region-card"}
              disabled={disabled || blocked}
              key={region}
              onClick={() => toggle(region)}
              type="button"
            >
              <span className="preferred-region-card-icon" aria-hidden="true">
                {getRegionIcon(region)}
              </span>
              <span className="preferred-region-card-label">{region}</span>
              {active && (
                <span className="preferred-region-card-check" aria-hidden="true">
                  ✓
                </span>
              )}
            </button>
          );
        })}
      </div>
      {isAtLimit && <p className="meta">관심 지역은 최대 {maxSelections}개까지 선택할 수 있어요.</p>}
    </div>
  );
}
