import { useEffect, useState } from "react";
import { CircleHelp, Dice5, FileText, KeyRound, LogOut, ShieldCheck, UserX } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { appDataApi, isApiError, type Policy, type Profile, type Trip } from "../api";
import { useSession } from "../app/session";
import { ProfilePreferencePreview } from "../components/ProfilePreferencePreview";
import { PreferredRegionSelector } from "../components/PreferredRegionSelector";
import { formatPreferredRegions, getPreferenceIcon } from "../components/preferenceDisplay";
import { FavoritePolicyCard, ProfileSectionHeader } from "../components/patterns";
import { Button, EmptyState, ErrorState, LoadingState } from "../components/ui";
import { useAsyncResource } from "../api/useAsyncResource";

type InfoSheetType = "faq" | "terms" | "privacy";

const WITHDRAW_CONFIRMATION_PHRASE = "탈퇴합니다";

function uniquePoliciesBySlug(policies: Policy[]) {
  const seen = new Set<string>();
  return policies.filter((policy) => {
    if (seen.has(policy.slug)) return false;
    seen.add(policy.slug);
    return true;
  });
}

function profileValueLabel(value: string | null | undefined) {
  return value?.trim() ? value : "미정";
}

function accountErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 401) return "현재 비밀번호를 확인해 주세요.";
    if (error.status === 400 && typeof error.detail === "string") return error.detail;
  }
  return fallback;
}

export function MyPage() {
  const navigate = useNavigate();
  const { addedPolicySlugs, currentUser, likedPolicy, logout, profile, removeSavedSlug, saveNickname, saveProfile, savedSlugs } = useSession();
  const { data: profileOptions } = useAsyncResource(() => appDataApi.getProfileOptions(), []);
  const { regions, travelStyles, budgets } = profileOptions ?? { regions: [], travelStyles: [], budgets: [] };
  const name = currentUser?.nickname ?? "여행자";
  const [savedPolicies, setSavedPolicies] = useState<Policy[]>([]);
  const [isLoadingSavedPolicies, setIsLoadingSavedPolicies] = useState(true);
  const [savedPolicyError, setSavedPolicyError] = useState("");
  const [trips, setTrips] = useState<Trip[]>([]);
  const [isLoadingTrips, setIsLoadingTrips] = useState(true);
  const [tripError, setTripError] = useState("");
  const [appliedPolicyCount, setAppliedPolicyCount] = useState(0);
  const [isLoadingAppliedPolicies, setIsLoadingAppliedPolicies] = useState(true);
  const [removingPolicySlug, setRemovingPolicySlug] = useState<string | null>(null);
  const [isProfileEditorOpen, setIsProfileEditorOpen] = useState(false);
  const [profileDraft, setProfileDraft] = useState<Profile>(() => profile);
  const [nicknameDraft, setNicknameDraft] = useState(name);
  const [nicknameError, setNicknameError] = useState("");
  const [isSuggestingNickname, setIsSuggestingNickname] = useState(false);
  const [isSavingProfile, setIsSavingProfile] = useState(false);
  const [profileEditError, setProfileEditError] = useState("");
  const [infoSheetType, setInfoSheetType] = useState<InfoSheetType | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordChangeError, setPasswordChangeError] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [withdrawPassword, setWithdrawPassword] = useState("");
  const [withdrawConfirmation, setWithdrawConfirmation] = useState("");
  const [withdrawError, setWithdrawError] = useState("");
  const [isWithdrawing, setIsWithdrawing] = useState(false);

  useEffect(() => {
    let isCurrent = true;
    setIsLoadingSavedPolicies(true);
    setSavedPolicyError("");
    setIsLoadingTrips(true);
    setTripError("");
    setIsLoadingAppliedPolicies(true);

    Promise.allSettled([
      appDataApi.listSavedPolicies(),
      appDataApi.listTrips(),
      appDataApi.listAppliedPolicies(),
    ]).then(([savedResult, tripsResult, appliedResult]) => {
      if (!isCurrent) return;

      if (savedResult.status === "fulfilled") setSavedPolicies(uniquePoliciesBySlug(savedResult.value));
      else setSavedPolicyError("저장한 정책을 불러오지 못했어요.");
      setIsLoadingSavedPolicies(false);

      if (tripsResult.status === "fulfilled") setTrips(tripsResult.value);
      else setTripError("일정 정보를 불러오지 못했어요.");
      setIsLoadingTrips(false);

      if (appliedResult.status === "fulfilled") setAppliedPolicyCount(appliedResult.value.length);
      else setAppliedPolicyCount(0);
      setIsLoadingAppliedPolicies(false);
    });

    return () => {
      isCurrent = false;
    };
  }, []);

  const signOut = async () => {
    await logout();
    navigate("/login");
  };

  const clearSessionAndRedirect = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const changePassword = async () => {
    setPasswordChangeError("");
    if (!currentPassword) {
      setPasswordChangeError("현재 비밀번호를 입력해 주세요.");
      return;
    }
    if (newPassword.length < 8) {
      setPasswordChangeError("새 비밀번호는 8자 이상 입력해 주세요.");
      return;
    }

    setIsChangingPassword(true);
    try {
      await appDataApi.changePassword({
        currentPassword,
        newPassword,
      });
      await clearSessionAndRedirect();
    } catch (error) {
      setPasswordChangeError(accountErrorMessage(error, "비밀번호를 변경하지 못했어요. 잠시 후 다시 시도해 주세요."));
    } finally {
      setIsChangingPassword(false);
    }
  };

  const withdrawAccount = async () => {
    setWithdrawError("");
    const hasPassword = currentUser?.hasPassword === true;
    if (hasPassword && !withdrawPassword) {
      setWithdrawError("탈퇴하려면 현재 비밀번호를 입력해 주세요.");
      return;
    }
    if (!hasPassword && withdrawConfirmation !== WITHDRAW_CONFIRMATION_PHRASE) {
      setWithdrawError(`탈퇴하려면 확인 문구 ${WITHDRAW_CONFIRMATION_PHRASE}를 정확히 입력해 주세요.`);
      return;
    }

    setIsWithdrawing(true);
    try {
      await appDataApi.withdraw(hasPassword ? { password: withdrawPassword } : { confirmationPhrase: withdrawConfirmation });
      await clearSessionAndRedirect();
    } catch (error) {
      setWithdrawError(accountErrorMessage(error, "회원 탈퇴를 처리하지 못했어요. 잠시 후 다시 시도해 주세요."));
    } finally {
      setIsWithdrawing(false);
    }
  };

  const removeSavedPolicy = async (policy: Policy) => {
    if (removingPolicySlug) return;
    setRemovingPolicySlug(policy.slug);
    setSavedPolicyError("");
    try {
      await appDataApi.removeSavedPolicy(policy.slug);
      setSavedPolicies((current) => current.filter((item) => item.slug !== policy.slug));
      removeSavedSlug(policy.slug);
    } catch {
      setSavedPolicyError("저장한 정책을 해제하지 못했어요.");
    } finally {
      setRemovingPolicySlug(null);
    }
  };

  const openProfileEditor = () => {
    setProfileDraft(profile);
    setNicknameDraft(currentUser?.nickname ?? name);
    setNicknameError("");
    setProfileEditError("");
    setIsProfileEditorOpen(true);
  };

  const suggestNickname = async () => {
    setNicknameError("");
    setIsSuggestingNickname(true);
    try {
      const suggestion = await appDataApi.getNicknameSuggestion();
      setNicknameDraft(suggestion.nickname);
    } catch {
      setNicknameError("닉네임을 추천하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSuggestingNickname(false);
    }
  };

  const saveProfileDraft = async () => {
    const trimmedNickname = nicknameDraft.trim();
    setNicknameError("");
    setProfileEditError("");
    if (trimmedNickname.length < 2 || trimmedNickname.length > 20) {
      setNicknameError("닉네임은 2자 이상 20자 이하로 입력해 주세요.");
      return;
    }

    const nicknameChanged = trimmedNickname !== (currentUser?.nickname ?? "").trim();
    setIsSavingProfile(true);
    if (nicknameChanged) {
      try {
        await saveNickname(trimmedNickname);
      } catch {
        setNicknameError("닉네임을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
        setIsSavingProfile(false);
        return;
      }
    }

    try {
      await saveProfile(profileDraft);
      setIsProfileEditorOpen(false);
    } catch {
      setProfileEditError("프로필을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSavingProfile(false);
    }
  };

  const visibleSavedPolicies = uniquePoliciesBySlug(savedPolicies);
  const savedPolicyCount = Math.max(visibleSavedPolicies.length, savedSlugs.size);
  const appliedPolicySummaryCount = Math.max(appliedPolicyCount, addedPolicySlugs.size);
  const tripCount = tripError ? 0 : trips.length;
  return (
    <section className="screen with-tabs prototype-mypage-screen">
      <div className="content stack padded prototype-mypage-content">
        <section className="ds-card ds-profile-panel prototype-profile-hero-card" aria-label="내 프로필 요약">
          <div className="prototype-profile-main">
            <div className="avatar large prototype-profile-badge" aria-hidden="true">
              🧳
            </div>
            <div className="prototype-profile-text">
              <h2 className="profile-name">{name}</h2>
              <p className="prototype-profile-email">{currentUser?.email ?? "이메일 정보 없음"}</p>
              <div className="prototype-profile-chips" aria-label="프로필 취향">
                <span>{formatPreferredRegions(profile.preferredRegions)}</span>
                <span>{profileValueLabel(profile.style)}</span>
                <span>{profileValueLabel(profile.budget)}</span>
              </div>
            </div>
            <button className="btn ghost prototype-profile-edit-button" onClick={openProfileEditor} type="button">
              편집
            </button>
          </div>
        </section>

        <section className="prototype-stat-grid" aria-label="나의 활동 요약">
          <ProfileStat label="내 일정" value={isLoadingTrips ? "..." : String(tripCount)} tone="primary" to="/trips" />
          <ProfileStat label="즐겨찾기" value={isLoadingSavedPolicies ? "..." : String(savedPolicyCount)} tone="secondary" to="/policies?saved=1" />
          <ProfileStat label="신청 정책" value={isLoadingAppliedPolicies ? "..." : String(appliedPolicySummaryCount)} tone="accent" to="/applied-policies" />
        </section>

        <section className="prototype-favorite-section" aria-label="즐겨찾기 정책">
          <ProfileSectionHeader title={`즐겨찾기 정책 (${isLoadingSavedPolicies ? "..." : savedPolicyCount})`} actionLabel="정책 찾기" to="/policies" />
          {isLoadingSavedPolicies && <LoadingState compact label="즐겨찾기 정책을 불러오는 중입니다" />}
          {!isLoadingSavedPolicies && savedPolicyError && (
            <ErrorState
              compact
              message={savedPolicyError}
              action={
                <Link className="btn line" to="/policies">
                  정책 찾기
                </Link>
              }
            />
          )}
          {!isLoadingSavedPolicies && !savedPolicyError && visibleSavedPolicies.length === 0 && (
            <div className="prototype-favorite-empty">
              <EmptyState
                compact
                eyebrow="즐겨찾기 정책"
                title="아직 즐겨찾기한 정책이 없어요"
                body="관심 있는 혜택의 하트를 눌러두면 여기에서 다시 확인할 수 있어요."
                action={
                  <Link className="btn line" to="/policies">
                    정책 보러가기
                  </Link>
                }
              />
            </div>
          )}
          {!isLoadingSavedPolicies && !savedPolicyError && visibleSavedPolicies.length > 0 && (
            <div className="prototype-favorite-list">
              {visibleSavedPolicies.map((policy) => (
                <FavoritePolicyCard
                  isRemoving={removingPolicySlug === policy.slug}
                  key={policy.slug}
                  onRemove={() => removeSavedPolicy(policy)}
                  policy={policy}
                />
              ))}
            </div>
          )}
        </section>

        <AccountSecuritySection
          currentPassword={currentPassword}
          error={passwordChangeError}
          hasPassword={currentUser?.hasPassword === true}
          isSubmitting={isChangingPassword}
          newPassword={newPassword}
          onChangeCurrentPassword={setCurrentPassword}
          onChangeNewPassword={setNewPassword}
          onSubmit={changePassword}
        />

        <AccountWithdrawalSection
          confirmation={withdrawConfirmation}
          error={withdrawError}
          hasPassword={currentUser?.hasPassword === true}
          isSubmitting={isWithdrawing}
          password={withdrawPassword}
          onChangeConfirmation={setWithdrawConfirmation}
          onChangePassword={setWithdrawPassword}
          onSubmit={withdrawAccount}
        />

        <section className="prototype-settings-menu ds-settings-menu" aria-label="설정 메뉴">
          <button className="prototype-menu-row" onClick={() => setInfoSheetType("faq")} type="button">
            <span className="prototype-menu-icon" aria-hidden="true">
              <CircleHelp size={18} />
            </span>
            <strong>공지사항 / FAQ</strong>
            <span className="prototype-menu-chevron" aria-hidden="true">
              ›
            </span>
          </button>
          <button className="prototype-menu-row" onClick={() => setInfoSheetType("terms")} type="button">
            <span className="prototype-menu-icon" aria-hidden="true">
              <FileText size={18} />
            </span>
            <strong>이용약관</strong>
            <span className="prototype-menu-chevron" aria-hidden="true">
              ›
            </span>
          </button>
          <button className="prototype-menu-row" onClick={() => setInfoSheetType("privacy")} type="button">
            <span className="prototype-menu-icon" aria-hidden="true">
              <ShieldCheck size={18} />
            </span>
            <strong>개인정보처리방침</strong>
            <span className="prototype-menu-chevron" aria-hidden="true">
              ›
            </span>
          </button>
          <button className="prototype-menu-row danger" onClick={signOut} type="button">
            <span className="prototype-menu-icon" aria-hidden="true">
              <LogOut size={18} />
            </span>
            <strong>로그아웃</strong>
            <span className="prototype-menu-chevron" aria-hidden="true">
              ›
            </span>
          </button>
        </section>

        {isProfileEditorOpen && (
          <ProfileEditSheet
            draft={profileDraft}
            error={profileEditError}
            isSaving={isSavingProfile}
            isSuggestingNickname={isSuggestingNickname}
            nickname={nicknameDraft}
            nicknameError={nicknameError}
            profilesRegions={regions}
            profilesTravelStyles={travelStyles}
            profilesBudgets={budgets}
            onCancel={() => !isSavingProfile && setIsProfileEditorOpen(false)}
            onChange={setProfileDraft}
            onNicknameChange={setNicknameDraft}
            onSave={saveProfileDraft}
            onSuggestNickname={suggestNickname}
          />
        )}


        {infoSheetType && <InfoSheet type={infoSheetType} onClose={() => setInfoSheetType(null)} />}
      </div>
    </section>
  );
}

function AccountSecuritySection({
  currentPassword,
  error,
  hasPassword,
  isSubmitting,
  newPassword,
  onChangeCurrentPassword,
  onChangeNewPassword,
  onSubmit,
}: {
  currentPassword: string;
  error: string;
  hasPassword: boolean;
  isSubmitting: boolean;
  newPassword: string;
  onChangeCurrentPassword: (value: string) => void;
  onChangeNewPassword: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="ds-card prototype-account-section" aria-labelledby="account-password-title">
      <div className="prototype-account-section-head">
        <span className="prototype-account-icon" aria-hidden="true">
          <KeyRound size={18} />
        </span>
        <div>
          <h2 id="account-password-title">비밀번호 관리</h2>
          <p className="meta">계정 보안을 위해 변경 후 다시 로그인해야 합니다.</p>
        </div>
      </div>
      {hasPassword ? (
        <div className="profile-edit-sections">
          <label className="field">
            <span>현재 비밀번호</span>
            <input
              autoComplete="current-password"
              disabled={isSubmitting}
              aria-label="현재 비밀번호"
              name="currentPassword"
              onChange={(event) => onChangeCurrentPassword(event.target.value)}
              type="password"
              value={currentPassword}
            />
          </label>
          <label className="field">
            <span>새 비밀번호</span>
            <input
              autoComplete="new-password"
              disabled={isSubmitting}
              aria-label="새 비밀번호"
              name="newPassword"
              onChange={(event) => onChangeNewPassword(event.target.value)}
              type="password"
              value={newPassword}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <Button disabled={isSubmitting} onClick={onSubmit}>
            {isSubmitting ? "변경 중입니다" : "비밀번호 변경"}
          </Button>
        </div>
      ) : (
        <div className="prototype-info-block">
          <strong>소셜 로그인 계정입니다</strong>
          <p>이 계정은 앱 비밀번호가 없어 비밀번호 변경을 제공하지 않습니다. 비밀번호와 로그인 보안은 연결한 소셜 제공자에서 관리해 주세요.</p>
        </div>
      )}
    </section>
  );
}

function AccountWithdrawalSection({
  confirmation,
  error,
  hasPassword,
  isSubmitting,
  password,
  onChangeConfirmation,
  onChangePassword,
  onSubmit,
}: {
  confirmation: string;
  error: string;
  hasPassword: boolean;
  isSubmitting: boolean;
  password: string;
  onChangeConfirmation: (value: string) => void;
  onChangePassword: (value: string) => void;
  onSubmit: () => void;
}) {
  return (
    <section className="ds-card danger prototype-account-section" aria-labelledby="account-withdraw-title">
      <div className="prototype-account-section-head">
        <span className="prototype-account-icon" aria-hidden="true">
          <UserX size={18} />
        </span>
        <div>
          <h2 id="account-withdraw-title">회원 탈퇴</h2>
          <p className="meta">탈퇴하면 계정이 비활성화되고 다시 로그인할 수 없습니다.</p>
        </div>
      </div>
      <div className="profile-edit-sections">
        <ul className="meta">
          <li>탈퇴 후 계정은 복구할 수 없습니다.</li>
          <li>같은 이메일로 다시 가입할 수 있습니다.</li>
          <li>새로 가입해도 이전 데이터는 복원되지 않습니다.</li>
        </ul>
        {hasPassword ? (
          <label className="field">
            <span>현재 비밀번호</span>
            <input
              autoComplete="current-password"
              disabled={isSubmitting}
              aria-label="현재 비밀번호"
              name="withdrawPassword"
              onChange={(event) => onChangePassword(event.target.value)}
              type="password"
              value={password}
            />
          </label>
        ) : (
          <label className="field">
            <span>확인 문구</span>
            <input
              autoComplete="off"
              disabled={isSubmitting}
              aria-label="확인 문구"
              name="withdrawConfirmation"
              onChange={(event) => onChangeConfirmation(event.target.value)}
              placeholder={WITHDRAW_CONFIRMATION_PHRASE}
              type="text"
              value={confirmation}
            />
            <small className="meta">탈퇴하려면 {WITHDRAW_CONFIRMATION_PHRASE}를 정확히 입력해 주세요.</small>
          </label>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <Button disabled={isSubmitting} onClick={onSubmit} variant="danger">
          {isSubmitting ? "탈퇴 처리 중입니다" : "회원 탈퇴"}
        </Button>
      </div>
    </section>
  );
}

function ProfileStat({
  label,
  tone,
  value,
  to,
}: {
  label: string;
  tone: "primary" | "secondary" | "accent";
  value: string;
  to?: string;
}) {
  const content = (
    <>
      <strong>{value}</strong>
      <span>{label}</span>
    </>
  );
  const className = `prototype-stat-card ${tone}`;

  if (to) {
    return (
      <Link aria-label={`${label} 보기`} className={className} to={to}>
        {content}
      </Link>
    );
  }

  return <div className={className}>{content}</div>;
}

const infoSheetContent: Record<InfoSheetType, { title: string; intro: string; sections: Array<{ heading: string; body: string }> }> = {
  faq: {
    title: "공지사항 / FAQ",
    intro: "트래블헌터 이용 전에 자주 확인하는 안내를 모았어요.",
    sections: [
      {
        heading: "정책 정보는 어떻게 확인하나요?",
        body: "정책 상세 화면에서 지원 내용, 신청 대상, 필요 서류, 마감일을 먼저 확인하고 공식 안내 링크에서 최종 조건을 확인해 주세요.",
      },
      {
        heading: "신청 버튼과 혜택 안내 보기 버튼은 무엇이 다른가요?",
        body: "신청 버튼은 접수 화면으로 바로 이동하는 링크이고, 혜택 안내 보기는 기관의 상세 안내 페이지로 이동하는 링크입니다.",
      },
      {
        heading: "즐겨찾기는 어디에 저장되나요?",
        body: "관심 정책의 하트를 누르면 마이페이지 즐겨찾기 정책에 저장되고 목록과 상세 화면 상태가 함께 동기화됩니다.",
      },
    ],
  },
  terms: {
    title: "이용약관",
    intro: "트래블헌터를 이용할 때 적용되는 기본 조건입니다.",
    sections: [
      {
        heading: "서비스 목적",
        body: "트래블헌터는 여행 지원 정책 탐색, 즐겨찾기, 일정 연결, 신청 준비 확인을 돕는 정보 제공 서비스입니다.",
      },
      {
        heading: "정보의 성격",
        body: "앱에 표시되는 정책 정보는 사용자의 탐색을 돕기 위한 요약 정보이며, 실제 신청 가능 여부는 공식 안내에서 최종 확인해야 합니다.",
      },
      {
        heading: "사용자 책임",
        body: "사용자는 신청 전 공식 안내 페이지에서 신청 기간, 대상 조건, 예산 소진 여부, 제출 서류를 직접 확인해야 합니다.",
      },
    ],
  },
  privacy: {
    title: "개인정보처리방침",
    intro: "트래블헌터 기능 제공에 필요한 개인정보 처리 기준입니다.",
    sections: [
      {
        heading: "수집 항목",
        body: "이메일, 닉네임, 프로필 선호 정보, 저장한 정책, 여행 일정, 초대 참여 정보를 기능 제공 범위에서 처리합니다.",
      },
      {
        heading: "이용 목적",
        body: "로그인, 회원 식별, 맞춤 정책 표시, 일정 관리, 즐겨찾기 동기화 기능 제공에 사용합니다.",
      },
      {
        heading: "보호 조치",
        body: "비밀번호와 재설정 토큰은 원문으로 저장하지 않고, 실제 운영 secret과 환경값은 저장소에 기록하지 않습니다.",
      },
    ],
  },
};

function InfoSheet({ onClose, type }: { onClose: () => void; type: InfoSheetType }) {
  const content = infoSheetContent[type];

  return (
    <div className="sheet-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="trip-select-sheet prototype-info-sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="mypage-info-sheet-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <div className="sheet-head">
          <div>
            <h2 id="mypage-info-sheet-title">{content.title}</h2>
            <p className="meta">{content.intro}</p>
          </div>
          <button className="btn sm ghost" type="button" onClick={onClose}>
            닫기
          </button>
        </div>

        <div className="prototype-info-sheet-content">
          {content.sections.map((section) => (
            <article className="prototype-info-block" key={section.heading}>
              <strong>{section.heading}</strong>
              <p>{section.body}</p>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function ProfileEditSheet({
  draft,
  error,
  isSaving,
  isSuggestingNickname,
  nickname,
  nicknameError,
  profilesRegions,
  profilesTravelStyles,
  profilesBudgets,
  onCancel,
  onChange,
  onNicknameChange,
  onSave,
  onSuggestNickname,
}: {
  draft: Profile;
  error: string;
  isSaving: boolean;
  isSuggestingNickname: boolean;
  nickname: string;
  nicknameError: string;
  profilesRegions: readonly string[];
  profilesTravelStyles: readonly string[];
  profilesBudgets: readonly string[];
  onCancel: () => void;
  onChange: (draft: Profile) => void;
  onNicknameChange: (nickname: string) => void;
  onSave: () => void;
  onSuggestNickname: () => void;
}) {
  return (
    <div className="sheet-backdrop" role="presentation" onMouseDown={onCancel}>
      <section className="trip-select-sheet" role="dialog" aria-modal="true" aria-labelledby="profile-editor-title" onMouseDown={(event) => event.stopPropagation()}>
        <div className="sheet-head">
          <div>
            <h2 id="profile-editor-title">프로필 편집</h2>
            <p className="meta">관심 지역, 여행 스타일, 예산을 바꾸면 추천 기준도 함께 바뀝니다.</p>
          </div>
          <button className="btn sm ghost" type="button" onClick={onCancel} disabled={isSaving}>
            취소
          </button>
        </div>
        <div className="profile-edit-sections">
          <ProfilePreferencePreview
            className="profile-edit-preference-preview"
            cta="저장하면 홈 추천과 맞춤 일정에 바로 반영됩니다."
            profile={draft}
          />
          <label className="field">
            <span>닉네임</span>
            <div className="input-action-row nickname-row">
              <input
                name="nickname"
                type="text"
                value={nickname}
                onChange={(event) => onNicknameChange(event.target.value)}
                maxLength={20}
                autoComplete="nickname"
                disabled={isSaving}
              />
              <button className="icon-btn" type="button" aria-label="랜덤 닉네임 추천" onClick={onSuggestNickname} disabled={isSaving || isSuggestingNickname}>
                <Dice5 size={18} />
              </button>
            </div>
          </label>
          {nicknameError && (
            <p className="form-error" role="alert">
              {nicknameError}
            </p>
          )}
          <div>
            <div className="choice-label">관심 지역</div>
            <PreferredRegionSelector
              compact
              disabled={isSaving}
              onChange={(preferredRegions) => onChange({ ...draft, preferredRegions: preferredRegions.length > 0 ? preferredRegions : null })}
              options={profilesRegions}
              value={draft.preferredRegions ?? []}
            />
          </div>
          <ProfileEditChoices
            label="여행 스타일"
            selected={draft.style}
            values={profilesTravelStyles}
            onSelect={(style) => onChange({ ...draft, style })}
            disabled={isSaving}
          />
          <ProfileEditChoices
            label="예산"
            selected={draft.budget}
            values={profilesBudgets}
            onSelect={(budget) => onChange({ ...draft, budget })}
            disabled={isSaving}
          />
          {error && <p className="form-error">{error}</p>}
        </div>
        <div className="sheet-actions">
          <Button full disabled={isSaving} onClick={onSave}>
            {isSaving ? "저장 중입니다" : "저장하기"}
          </Button>
        </div>
      </section>
    </div>
  );
}

function ProfileEditChoices({
  disabled = false,
  label,
  onSelect,
  selected,
  values,
}: {
  disabled?: boolean;
  label: string;
  onSelect: (value: string) => void;
  selected: string | null;
  values: readonly string[];
}) {
  return (
    <div>
      <div className="choice-label">{label}</div>
      <div className="preference-choice-grid profile-edit-choice-grid">
        {values.map((value) => (
          <button
            aria-pressed={selected === value}
            className={selected === value ? "preference-choice-card active" : "preference-choice-card"}
            disabled={disabled}
            key={value}
            onClick={() => onSelect(value)}
            type="button"
          >
            <span className="preference-choice-icon" aria-hidden="true">
              {getPreferenceIcon(value)}
            </span>
            {value}
          </button>
        ))}
      </div>
    </div>
  );
}
