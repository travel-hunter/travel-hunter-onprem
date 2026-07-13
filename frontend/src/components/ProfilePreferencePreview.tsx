import type { Profile } from "../api";
import { formatPreferredRegions, formatProfilePreference } from "./preferenceDisplay";

export function ProfilePreferencePreview({
  className = "",
  cta = "홈 AI 추천 맞춤 일정에 이 기준이 적용됩니다.",
  profile,
}: {
  className?: string;
  cta?: string;
  profile: Pick<Profile, "preferredRegions" | "style" | "budget">;
}) {
  const regions = formatPreferredRegions(profile.preferredRegions);
  const style = formatProfilePreference(profile.style, "스타일 미정");
  const budget = formatProfilePreference(profile.budget, "예산 미정");

  return (
    <section className={["profile-preference-preview", className].filter(Boolean).join(" ")} aria-label="현재 추천 기준">
      <div>
        <span className="profile-preference-preview-kicker">현재 추천 기준</span>
        <strong>{regions}</strong>
      </div>
      <div className="profile-preference-preview-chips" aria-label="추천 기준 요약">
        <span>{style}</span>
        <span>{budget}</span>
      </div>
      <p>{cta}</p>
    </section>
  );
}
