import { Heart } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Policy, Trip } from "../api";
import { getPolicyMoodIcon, getPolicyMoodTone, getTripRegionEmojiFromTitle } from "../data/displayConfig";
import { dday } from "../utils";
import { canUsePolicyActions } from "../utils/policyCapabilities";
import { SurfaceCard, Tag } from "./ui";

function compactDeadline(deadline: string) {
  return `~${deadline.split("-").join(".")}`;
}

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

  return (
    <SurfaceCard as="article" className="policy-list-card">
      <Link className="policy-list-card-link" to={`/policies/${policy.slug}`}>
        <div className={`policy-list-icon ${getPolicyMoodTone(policy)}`}>{getPolicyMoodIcon(policy)}</div>
        <div className="policy-list-copy">
          <div className="policy-list-badges">
            <span>{policy.amount}</span>
            <em>{dday(policy.deadline)}</em>
          </div>
          <h3>{policy.title}</h3>
          <div className="policy-list-meta">
            <span aria-hidden="true">📍</span>
            {policy.region} · {compactDeadline(policy.deadline)}
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
  const totalPlaces = Object.values(trip.days).reduce((sum, places) => sum + places.length, 0);
  const dayCount = Object.keys(trip.days).length || 1;
  const participantNames = tripParticipantNames(trip);
  const participantCount = participantNames.length;

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
          <div className="itinerary-actions">
            {onDelete && (
              <button className="trip-delete-btn" disabled={isDeleting} onClick={() => onDelete(trip)} type="button">
                {isDeleting ? "삭제 중" : "삭제"}
              </button>
            )}
          </div>
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
            <Tag tone="benefit">예상 혜택 {trip.expectedSaving}</Tag>
          </div>
        </Link>
      </div>
    </SurfaceCard>
  );
}
