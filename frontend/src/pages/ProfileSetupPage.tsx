import { useState } from "react";
import { ChevronLeft } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { appDataApi } from "../api";
import { getSafeRedirect, withRedirect } from "../app/onboarding";
import { useSession } from "../app/session";
import { useAsyncResource } from "../api/useAsyncResource";
import { ProfilePreferencePreview } from "../components/ProfilePreferencePreview";
import { PreferredRegionSelector } from "../components/PreferredRegionSelector";
import { getPreferenceIcon } from "../components/preferenceDisplay";
import { Button, ErrorState, IconButton } from "../components/ui";

type ProfileSetupField = "preferredRegions" | "style" | "budget";

export function ProfileSetupPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { profile, updateProfile, saveProfile, skipProfileSetup } = useSession();
  const { data: profileOptions, error: profileOptionsError, isLoading: profileOptionsLoading } = useAsyncResource(
    () => appDataApi.getProfileOptions(),
    [],
  );
  const [stepIndex, setStepIndex] = useState(0);
  const [isSaving, setIsSaving] = useState(false);
  const [isSkipping, setIsSkipping] = useState(false);
  const [error, setError] = useState("");

  const steps = [
    {
      key: "preferredRegions" as ProfileSetupField,
      label: "지역",
      title: "어디로 떠나고 싶나요?",
      body: "관심 지역을 기준으로 정책과 일정을 먼저 추천합니다.",
      choices: profileOptions?.regions ?? [],
    },
    {
      key: "style" as ProfileSetupField,
      label: "스타일",
      title: "어떤 여행을 선호하나요?",
      body: "장소와 동선을 맞출 때 여행 스타일을 반영합니다.",
      choices: profileOptions?.travelStyles ?? [],
    },
    {
      key: "budget" as ProfileSetupField,
      label: "예산",
      title: "예산 범위를 알려주세요",
      body: "예산에 맞는 혜택과 예약 옵션을 보여드립니다.",
      choices: profileOptions?.budgets ?? [],
    },
  ];

  const step = steps[stepIndex];
  const redirect = getSafeRedirect(searchParams);

  if (profileOptionsLoading || !profileOptions) {
    return (
      <section className="screen">
        <div className="top-bar">
          <IconButton label="뒤로" onClick={() => navigate("/nickname-setup")}>
            <ChevronLeft size={20} />
          </IconButton>
          <h1>정보 입력</h1>
          <span className="meta top-count">1/3</span>
        </div>
        <div className="content stack padded">
          <ErrorState compact message="프로필 항목을 불러오는 중입니다." />
        </div>
      </section>
    );
  }

  if (profileOptionsError) {
    return (
      <section className="screen">
        <div className="top-bar">
          <IconButton label="뒤로" onClick={() => navigate("/nickname-setup")}>
            <ChevronLeft size={20} />
          </IconButton>
          <h1>정보 입력</h1>
          <span className="meta top-count">1/3</span>
        </div>
        <div className="content stack padded">
          <ErrorState compact message={profileOptionsError} />
        </div>
      </section>
    );
  }

  const next = async () => {
    setError("");
    if (stepIndex !== steps.length - 1) {
      setStepIndex((current) => current + 1);
      return;
    }

    setIsSaving(true);
    try {
      await saveProfile(profile);
      navigate(redirect ?? "/home");
    } catch {
      setError("맞춤 추천 설정을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSaving(false);
    }
  };

  const finishLater = async () => {
    setError("");
    setIsSkipping(true);
    try {
      await skipProfileSetup();
      navigate(redirect ?? "/home");
    } catch {
      setError("나중에 설정 상태를 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSkipping(false);
    }
  };

  const back = () => {
    if (stepIndex === 0) navigate(withRedirect("/nickname-setup", redirect));
    else setStepIndex((current) => current - 1);
  };

  return (
    <section className="screen profile-setup-preference-screen">
      <div className="top-bar">
        <IconButton label="뒤로" onClick={back}>
          <ChevronLeft size={20} />
        </IconButton>
        <h1>정보 입력</h1>
        <span className="meta top-count">{stepIndex + 1}/3</span>
      </div>
      <div className="content stack padded">
        <div className="progress-bar">
          <div className="progress-fill" style={{ width: `${((stepIndex + 1) / steps.length) * 100}%` }} />
        </div>
        <div className="profile-setup-step-tabs" aria-label="프로필 설정 단계">
          {steps.map((candidate, index) => (
            <span className={index === stepIndex ? "active" : ""} key={candidate.key}>
              {index + 1}. {candidate.label}
            </span>
          ))}
        </div>
        <ProfilePreferencePreview profile={profile} />
        <section className="profile-setup-preference-card" aria-labelledby="profile-setup-step-title">
          <div className="eyebrow">맞춤 추천 설정</div>
          <h2 id="profile-setup-step-title">{step.title}</h2>
          <p>{step.body}</p>
          {step.key === "preferredRegions" ? (
            <PreferredRegionSelector
              onChange={(regions) => updateProfile("preferredRegions", regions.length > 0 ? regions : null)}
              options={step.choices}
              value={profile.preferredRegions ?? []}
            />
          ) : (
            <div className="preference-choice-grid">
              {step.choices.map((choice) => (
                <button
                  aria-pressed={profile[step.key] === choice}
                  className={profile[step.key] === choice ? "preference-choice-card active" : "preference-choice-card"}
                  key={choice}
                  onClick={() => updateProfile(step.key, choice)}
                  type="button"
                >
                  <span className="preference-choice-icon" aria-hidden="true">
                    {getPreferenceIcon(choice)}
                  </span>
                  {choice}
                </button>
              ))}
            </div>
          )}
        </section>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <Button full disabled={isSaving || isSkipping} onClick={next}>
          {isSaving ? "저장 중입니다" : stepIndex === steps.length - 1 ? "추천 홈 보기" : "다음"}
        </Button>
        <Button full variant="ghost" disabled={isSaving || isSkipping} onClick={finishLater}>
          {isSkipping ? "건너뛰는 중입니다" : "나중에 설정"}
        </Button>
      </div>
    </section>
  );
}
