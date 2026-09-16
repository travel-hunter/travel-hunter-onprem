import { useState } from "react";
import {
  ApiError,
  type TripPolicyApplication,
  type TripPolicyApplicationStatus,
  type TripPolicyApplicationUpdate,
} from "../api";
import { daysUntilPolicyDeadline, dday } from "../utils";
import { Tag } from "./ui";

export const APPLICATION_STATUS_LABEL: Record<TripPolicyApplicationStatus, string> = {
  not_started: "시작 전",
  applied: "신청함",
  selected: "선정됨",
  not_selected: "미선정",
  traveled: "여행 완료",
  documents_submitted: "서류 제출함",
  paid: "지급 완료",
};

const STEP_ORDER: Record<TripPolicyApplicationStatus, number> = {
  not_started: 0,
  applied: 1,
  selected: 2,
  not_selected: 2,
  traveled: 3,
  documents_submitted: 4,
  paid: 5,
};

const STEPS = ["신청", "선정", "섬 여행", "서류 제출", "지원금 수령"];

const NEXT_ACTIONS: Record<TripPolicyApplicationStatus, { label: string; status: TripPolicyApplicationStatus }[]> = {
  not_started: [{ label: "신청 완료로 표시", status: "applied" }],
  applied: [
    { label: "선정됨", status: "selected" },
    { label: "미선정", status: "not_selected" },
  ],
  selected: [{ label: "여행 완료로 표시", status: "traveled" }],
  not_selected: [],
  traveled: [{ label: "서류 제출 완료로 표시", status: "documents_submitted" }],
  documents_submitted: [{ label: "지급 확인", status: "paid" }],
  paid: [],
};

const PREVIOUS_STATUS: Partial<Record<TripPolicyApplicationStatus, TripPolicyApplicationStatus>> = {
  applied: "not_started",
  selected: "applied",
  not_selected: "applied",
  traveled: "selected",
  documents_submitted: "traveled",
  paid: "documents_submitted",
};

const DOCUMENTS_PENDING: TripPolicyApplicationStatus[] = ["not_started", "applied", "selected", "traveled"];

function dueTone(isoDate: string) {
  const days = daysUntilPolicyDeadline(isoDate);
  if (days === null) return "default" as const;
  if (days < 0) return "gray" as const;
  return days <= 3 ? ("warning" as const) : ("default" as const);
}

function checkLine(value: boolean | null, ok: string, warn: string) {
  if (value === null) return null;
  return <li className={value ? "ok" : "warn"}>{value ? `✓ ${ok}` : `⚠ ${warn}`}</li>;
}

/** Team-level island support progress on the trip page. Evidence files never go through the app. */
export function TripPolicyApplicationPanel({
  application,
  canEdit,
  onConflict,
  onSave,
  policyTitle,
}: {
  application: TripPolicyApplication;
  canEdit: boolean;
  onConflict: () => void;
  onSave: (patch: TripPolicyApplicationUpdate) => Promise<unknown>;
  policyTitle: string;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const { checks, status } = application;
  const currentStep = STEP_ORDER[status];

  const save = async (patch: TripPolicyApplicationUpdate) => {
    setSaving(true);
    setError("");
    try {
      await onSave(patch);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 409) {
        setError("다른 사람이 먼저 진행 상태를 바꿨어요. 최신 상태를 다시 불러왔어요.");
        onConflict();
      } else {
        setError("진행 상태를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
      }
    } finally {
      setSaving(false);
    }
  };

  const previous = PREVIOUS_STATUS[status];
  const applyDate = checks.applyDeadline ? checks.applyDeadline.slice(0, 10) : null;

  return (
    <section aria-label={`${policyTitle} 신청 진행`} className="trip-policy-application" role="region">
      <div className="trip-policy-application-head">
        <strong>{`현재 단계 · ${APPLICATION_STATUS_LABEL[status]}`}</strong>
        {status === "not_started" && applyDate && (
          <Tag tone={dueTone(applyDate)}>{`신청 마감 ${dday(applyDate)}`}</Tag>
        )}
        {checks.documentsDueDate && DOCUMENTS_PENDING.includes(status) && (
          <Tag tone={dueTone(checks.documentsDueDate)}>{`서류 제출 ${dday(checks.documentsDueDate)}`}</Tag>
        )}
      </div>

      <ol aria-label="신청 진행 단계" className="trip-policy-application-steps">
        {STEPS.map((label, index) => (
          <li className={index < currentStep ? "done" : index === currentStep ? "current" : undefined} key={label}>
            {label}
          </li>
        ))}
      </ol>

      <ul aria-label="일정 조건 점검" className="trip-policy-application-checks">
        {checkLine(checks.inTravelWindow, "일정이 이번 회차 여행 기간 안이에요", "일정이 이번 회차 여행 기간을 벗어나요")}
        {checkLine(checks.meetsMinNights, "1박 이상 일정이에요", "당일치기 일정은 지원 대상이 아니에요 (1박 이상)")}
        {checkLine(
          checks.eligibleIslandMatched,
          "일정에 대상 섬이 들어 있어요",
          "일정에 대상 섬이 없어요 (장소 이름이 대상 섬 이름과 같아야 해요)",
        )}
      </ul>

      {canEdit ? (
        <div className="trip-policy-application-actions">
          {NEXT_ACTIONS[status].map((action) => (
            <button
              className="btn primary"
              disabled={saving}
              key={action.status}
              onClick={() => void save({ status: action.status })}
              type="button"
            >
              {action.label}
            </button>
          ))}
          {previous && (
            <button className="btn secondary" disabled={saving} onClick={() => void save({ status: previous })} type="button">
              이전 단계로
            </button>
          )}
        </div>
      ) : (
        <p className="trip-policy-application-meta">보기 권한이라 진행 상태를 바꿀 수 없어요</p>
      )}

      {application.checklist.length > 0 && (
        <fieldset className="trip-policy-application-checklist">
          <legend>필요 서류 준비</legend>
          {application.checklist.map((item) => (
            <label key={item.key}>
              <input
                checked={item.checked}
                disabled={!canEdit || saving}
                onChange={(event) => void save({ checklist: { [item.key]: event.target.checked } })}
                type="checkbox"
              />
              {item.label}
            </label>
          ))}
          <p className="trip-policy-application-meta">
            증빙은 이 앱에 올리지 않고 공식 구글 폼에 제출해요. 사진은 이름·주민등록번호·날짜·금액이 보이게 찍어 주세요.
          </p>
        </fieldset>
      )}

      {application.updatedBy && <p className="trip-policy-application-meta">{`마지막 변경 · ${application.updatedBy}`}</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </section>
  );
}
