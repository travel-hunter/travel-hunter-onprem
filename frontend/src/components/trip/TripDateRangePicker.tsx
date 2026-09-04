import { useState } from "react";

import {
  addTripMonths,
  buildCalendarDays,
  formatTripCalendarMonth,
  formatTripDate,
  isTripDateInRange,
  normalizeSelectedRange,
  startOfTripMonth,
  tripDateDayCount,
  type TripDateRangeValue,
} from "../../utils/tripDateRange";

const calendarWeekdayLabels = ["일", "월", "화", "수", "목", "금", "토"];

type TripDateRangePickerProps = {
  value: TripDateRangeValue;
  onChange: (value: TripDateRangeValue) => void;
  disabled?: boolean;
  error?: string;
};

/* 일정 생성·직접 편집·상세 기간 수정이 함께 쓰는 범위 달력.
   controlled component 다. 내부에 남기는 상태는 열림 여부, 표시 중인 달,
   그리고 "지금 첫날을 고르는 중인지"뿐이다. */
export function TripDateRangePicker({
  value,
  onChange,
  disabled = false,
  error,
}: TripDateRangePickerProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() =>
    startOfTripMonth(value.startDate),
  );
  const [isPickingStart, setIsPickingStart] = useState(true);
  /* 첫 클릭한 날을 따로 들고 있는다. 부모가 value 를 곧바로 되돌려주지 않아도
     두 번째 클릭에서 올바른 범위를 만들 수 있어야 한다. */
  const [pendingStart, setPendingStart] = useState<string | null>(null);

  const dayCount = tripDateDayCount(value.startDate, value.endDate);

  const openCalendar = () => {
    if (disabled) return;
    setCalendarMonth(startOfTripMonth(value.startDate));
    setIsPickingStart(true);
    setPendingStart(null);
    setIsOpen(true);
  };

  const selectDate = (selected: string) => {
    setCalendarMonth(startOfTripMonth(selected));
    if (isPickingStart) {
      // 첫 클릭은 시작과 끝을 같은 날로 모은다. 중간 상태에서 범위가 뒤집히지 않는다.
      setPendingStart(selected);
      setIsPickingStart(false);
      onChange({ startDate: selected, endDate: selected });
      return;
    }
    const base = pendingStart ?? value.startDate;
    setPendingStart(null);
    setIsPickingStart(true);
    onChange(normalizeSelectedRange(base, selected));
  };

  return (
    <>
      <button
        aria-controls="trip-date-range-picker"
        aria-expanded={isOpen}
        className="trip-date-range-card"
        data-testid="trip-date-range-trigger"
        disabled={disabled}
        onClick={openCalendar}
        type="button"
      >
        <span>여행 날짜</span>
        <strong data-testid="trip-date-range-summary">
          {value.startDate} ~ {value.endDate}
        </strong>
        <em>{dayCount ? `${dayCount}일` : "날짜를 선택하세요"}</em>
      </button>
      {isOpen && (
        <div
          aria-label="여행 날짜 범위"
          className="trip-date-calendar"
          data-testid="trip-date-range-calendar"
          id="trip-date-range-picker"
          role="dialog"
        >
          <div className="trip-date-calendar-head">
            <button
              aria-label="이전 달"
              onClick={() =>
                setCalendarMonth((current) => addTripMonths(current, -1))
              }
              type="button"
            >
              이전
            </button>
            <strong>{formatTripCalendarMonth(calendarMonth)}</strong>
            <button
              aria-label="다음 달"
              onClick={() =>
                setCalendarMonth((current) => addTripMonths(current, 1))
              }
              type="button"
            >
              다음
            </button>
          </div>
          <p className="trip-date-calendar-guide">
            {isPickingStart ? "첫날을 선택하세요" : "마지막 날을 선택하세요"}
          </p>
          <div className="trip-date-calendar-grid" role="grid">
            {calendarWeekdayLabels.map((label) => (
              <span className="trip-date-weekday" key={label}>
                {label}
              </span>
            ))}
            {buildCalendarDays(calendarMonth).map((date) => {
              const selected = formatTripDate(date);
              const isCurrentMonth =
                date.getMonth() === calendarMonth.getMonth();
              const className = [
                "trip-date-day",
                isCurrentMonth ? "" : "outside-month",
                isTripDateInRange(selected, value.startDate, value.endDate)
                  ? "in-range"
                  : "",
                selected === value.startDate ? "range-start" : "",
                selected === value.endDate ? "range-end" : "",
              ]
                .filter(Boolean)
                .join(" ");
              return (
                <button
                  aria-label={selected}
                  className={className}
                  key={selected}
                  onClick={() => selectDate(selected)}
                  type="button"
                >
                  {date.getDate()}
                </button>
              );
            })}
          </div>
          <button
            className="trip-date-calendar-done"
            onClick={() => setIsOpen(false)}
            type="button"
          >
            완료
          </button>
        </div>
      )}
      {error && <p className="prototype-checkout-error">{error}</p>}
    </>
  );
}
