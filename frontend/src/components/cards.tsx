import { Heart, MoreHorizontal } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Policy, Trip } from "../api";
import { getPolicyMoodIcon, getPolicyMoodTone, getPolicyPhoto, getTripRegionEmojiFromTitle } from "../data/displayConfig";
import { PolicyThumbPhoto } from "./policyPhoto";
import { formatPolicyDeadlineTag, formatPolicyPeriodSummary, hasPolicySaving, isDigitalTourismResidentCardPolicy, tripStatus, type TripStatus } from "../utils";
import { canUsePolicyActions } from "../utils/policyCapabilities";
import { SurfaceCard, Tag } from "./ui";

function compactPolicyPeriod(policy: Policy) {
  return formatPolicyPeriodSummary(policy);
}

const TRIP_STATUS_TONE = { past: "gray", now: "green", urgent: "danger", soon: "primary" } as const satisfies Record<TripStatus["tone"], string>;

function tripRegionEmoji(trip: Trip) {
  return getTripRegionEmojiFromTitle(trip.title);
}

function tripParticipantNames(trip: Trip) {
  const names = trip.people.map((name) => name.trim()).filter(Boolean);
  return names.length ? names : ["나"];
}

function participantInitial(name: string) {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "?";
}

function participantPreview(names: string[]) {
  if (names.length <= 2) return names.join(", ");
  return `${names.slice(0, 2).join(", ")} 외 ${names.length - 2}명`;
}

export function PolicyListCard({
  policy,
  isSaved = false,
  onToggleSave,
}: {
  policy: Policy;
  isSaved?: boolean;
  onToggleSave?: (policy: Policy) => Promise<void>;
}) {
  const [isSaving, setIsSaving] = useState(false);

  const handleToggle = async (event: React.MouseEvent) => {
    event.preventDefault();
    if (isSaving || !onToggleSave) return;
    setIsSaving(true);
    try {
      await onToggleSave(policy);
    } finally {
      setIsSaving(false);
    }
  };
  const canSave = canUsePolicyActions(policy) && Boolean(onToggleSave);
  const periodSummary = compactPolicyPeriod(policy);
  const photo = getPolicyPhoto(policy);

  return (
    <SurfaceCard as="article" className="policy-list-card">
      <Link className="policy-list-card-link" to={`/policies/${policy.slug}`}>
        <div className={`policy-list-icon policy-list-media ${getPolicyMoodTone(policy)}`}>
          {photo ? (
            <PolicyThumbPhoto fallback={getPolicyMoodIcon(policy)} photo={photo} />
          ) : (
            getPolicyMoodIcon(policy)
          )}
        </div>
        <div className="policy-list-copy">
          <div className="policy-list-badges">
            {/* 카드에는 승인·검증된 문구만. 없으면 알약을 그리지 않는다 - amount 로 되돌아가면 오염 문장이 다시 뜬다 */}
            {policy.cardSummary ? <span>{policy.cardSummary}</span> : null}
            {/* 정책 탭 안의 짧은 칩은 주민증을 '상시'로(2026-09-30 사용자 결정). 상세 기간 칸만 '상시 발급' */}
            <em>{isDigitalTourismResidentCardPolicy(policy) ? "상시" : formatPolicyDeadlineTag(policy)}</em>
          </div>
          <h3>{policy.title}</h3>
          <div className="policy-list-meta">
            <span aria-hidden="true">📍</span>
            {periodSummary ? `${policy.region} · ${periodSummary}` : policy.region}
          </div>
        </div>
      </Link>
      {canSave && (
        <button
          className={isSaved ? "policy-list-heart saved" : "policy-list-heart"}
          disabled={isSaving}
          onClick={handleToggle}
          type="button"
          aria-label={isSaved ? `${policy.title} 즐겨찾기 해제` : `${policy.title} 즐겨찾기`}
          aria-pressed={isSaved}
        >
          <Heart size={20} fill={isSaved ? "currentColor" : "none"} />
        </button>
      )}
    </SurfaceCard>
  );
}

export function ItineraryCard({
  trip,
  addedPolicy = false,
  isDeleting = false,
  onDelete,
}: {
  trip: Trip;
  addedPolicy?: boolean;
  isDeleting?: boolean;
  onDelete?: (trip: Trip) => void;
}) {
  const detailPath = `/trips/${trip.id}`;
  const editPath = `/trips/${trip.id}/edit`;
  const totalPlaces = Object.values(trip.days).reduce((sum, places) => sum + places.length, 0);
  const dayCount = Object.keys(trip.days).length || 1;
  const participantNames = tripParticipantNames(trip);
  const participantCount = participantNames.length;
  const canEdit = trip.currentUserRole !== "viewer";
  const status = tripStatus(trip.startDate, trip.endDate);
  const recommendedCount = trip.recommendedPolicies.length;
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <SurfaceCard as="article" className="itinerary-card">
      <Link className="map-thumb" to={detailPath} aria-label={`${trip.title} 상세 보기`}>
        <span className="trip-visual-emoji" aria-hidden="true">
          {tripRegionEmoji(trip)}
        </span>
      </Link>
      <div className="itinerary-body">
        <div className="itinerary-head">
          <Link className="itinerary-title-link" to={detailPath}>
            <h4>{trip.title}</h4>
          </Link>
          {/* 편집·삭제는 자주 안 쓰는데 카드마다 버튼 둘이 제일 눈에 띄었다. ⋯ 하나로 접는다.
              밖으로 초점이 나가거나 Esc 면 닫힌다. */}
          {(canEdit || onDelete) && (
            <div
              className="itinerary-actions itinerary-card-menu"
              onBlur={(event) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setIsMenuOpen(false);
              }}
              onKeyDown={(event) => {
                if (event.key === "Escape") setIsMenuOpen(false);
              }}
            >
              <button
                aria-expanded={isMenuOpen}
                aria-label={`${trip.title} 편집·삭제`}
                className="itinerary-card-menu-toggle"
                onClick={() => setIsMenuOpen((open) => !open)}
                type="button"
              >
                <MoreHorizontal size={20} aria-hidden="true" />
              </button>
              {/* 넓은 화면(1024px 이상)에서는 가운데 창으로 뜬다 - 바탕을 누르면 닫히고 창에 일정 이름이 붙는다.
                  좁은 화면에선 바탕·이름이 CSS 로 숨어 지금처럼 카드 옆 작은 목록이다. */}
              {isMenuOpen && (
                <button
                  aria-hidden="true"
                  className="itinerary-card-menu-scrim"
                  onClick={() => setIsMenuOpen(false)}
                  tabIndex={-1}
                  type="button"
                />
              )}
              {isMenuOpen && (
                <div className="itinerary-card-menu-list">
                  <strong className="itinerary-card-menu-title">{trip.title}</strong>
                  {canEdit && <Link to={editPath}>일정 편집</Link>}
                  {onDelete && (
                    <button
                      className="danger"
                      disabled={isDeleting}
                      onClick={() => {
                        setIsMenuOpen(false);
                        onDelete(trip);
                      }}
                      type="button"
                    >
                      {isDeleting ? "삭제 중" : "일정 삭제"}
                    </button>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <Link to={detailPath}>
          <div className="meta">
            📅 {trip.dates} · {dayCount}일 · 장소 {totalPlaces}개
          </div>
          <div
            className="itinerary-participants"
            aria-label={`참여자 ${participantCount}명`}
          >
            <div className="itinerary-participant-avatars" aria-hidden="true">
              {participantNames.slice(0, 3).map((name, index) => (
                <span className="avatar-mini" key={`${name}-${index}`}>
                  {participantInitial(name)}
                </span>
              ))}
            </div>
            <div className="itinerary-participant-copy">
              <span>
                {participantCount}명 참여 중{addedPolicy ? " · 정책 연결됨" : ""}
              </span>
              <small>{participantPreview(participantNames)}</small>
            </div>
          </div>
          <div className="itinerary-policy-row">
            {status && <Tag tone={TRIP_STATUS_TONE[status.tone]}>{status.label}</Tag>}
            {recommendedCount > 0 && <Tag tone="benefit">추천 혜택 {recommendedCount}건</Tag>}
            {hasPolicySaving(trip.expectedSaving) && <Tag tone="benefit">예상 혜택 {trip.expectedSaving}</Tag>}
          </div>
        </Link>
      </div>
    </SurfaceCard>
  );
}
