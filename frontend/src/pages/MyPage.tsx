import { type ReactNode, useEffect, useRef, useState } from "react";
import { ChevronRight, CircleHelp, FileText, Heart, KeyRound, LogOut, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { appDataApi, isApiError, type Policy, type Trip } from "../api";
import { useSession } from "../app/session";
import { BenefitTile, benefitTypeOf } from "../components/benefitTile";
import { deadlineChip, programName, REGION_FULL_NAMES } from "../components/map/policyBrowse";
import { policyListText } from "../components/map/policyListText";
import { useProfileEditor } from "../components/ProfileEditSheet";
import { Button, ErrorState, LoadingState } from "../components/ui";
import { cityOf, NATIONWIDE_REGION } from "../utils/policyPrograms";
import "../styles/account.css";

type InfoSheetType = "faq" | "terms" | "privacy";
type AccountDialogType = "password" | "withdrawal";

const WITHDRAW_CONFIRMATION_PHRASE = "탈퇴합니다";

function uniquePoliciesBySlug(policies: Policy[]) {
  const seen = new Set<string>();
  return policies.filter((policy) => {
    if (seen.has(policy.slug)) return false;
    seen.add(policy.slug);
    return true;
  });
}

function accountErrorMessage(error: unknown, fallback: string) {
  if (isApiError(error)) {
    if (error.status === 401) return "현재 비밀번호를 확인해 주세요.";
    if (error.status === 400 && typeof error.detail === "string") return error.detail;
  }
  return fallback;
}

/* 내 정보(시안 v49): 앱 순서 그대로(프로필 → 활동 세 칸 → 즐겨찾기 → 설정)에 점검 보고서 문제만 고쳤다 -
   활동 칸은 숫자만 강조색, '신청 정책'은 실제 뜻대로 '담은 혜택'(/api/me/applied-policies 는 일정에 담은 혜택) + 그 목록,
   로그아웃은 보통 줄, 회원 탈퇴는 맨 아래 작은 글자. 넓은 화면은 왼쪽 프로필·설정 + 오른쪽 목록 두 단(account.css). */
export function MyPage() {
  const navigate = useNavigate();
  const { addedPolicySlugs, currentUser, logout, profile, removeSavedSlug, savedSlugs } = useSession();
  const editor = useProfileEditor();
  const name = currentUser?.nickname ?? "여행자";
  const [savedPolicies, setSavedPolicies] = useState<Policy[]>([]);
  const [isLoadingSavedPolicies, setIsLoadingSavedPolicies] = useState(true);
  const [savedPolicyError, setSavedPolicyError] = useState("");
  const [trips, setTrips] = useState<Trip[]>([]);
  const [isLoadingTrips, setIsLoadingTrips] = useState(true);
  const [tripError, setTripError] = useState("");
  const [appliedPolicies, setAppliedPolicies] = useState<Policy[]>([]);
  const [isLoadingAppliedPolicies, setIsLoadingAppliedPolicies] = useState(true);
  const [appliedPolicyError, setAppliedPolicyError] = useState(false);
  const [removingPolicySlug, setRemovingPolicySlug] = useState<string | null>(null);
  const [infoSheetType, setInfoSheetType] = useState<InfoSheetType | null>(null);
  const [accountDialogType, setAccountDialogType] = useState<AccountDialogType | null>(null);
  const [isWithdrawConfirmationOpen, setIsWithdrawConfirmationOpen] = useState(false);
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
    setAppliedPolicyError(false);

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

      if (appliedResult.status === "fulfilled") setAppliedPolicies(uniquePoliciesBySlug(appliedResult.value));
      else setAppliedPolicyError(true);
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

  const closePasswordDialog = () => {
    if (isChangingPassword) return;
    setAccountDialogType(null);
    setCurrentPassword("");
    setNewPassword("");
    setPasswordChangeError("");
  };

  const closeWithdrawalDialog = () => {
    if (isWithdrawing) return;
    setAccountDialogType(null);
    setIsWithdrawConfirmationOpen(false);
    setWithdrawPassword("");
    setWithdrawConfirmation("");
    setWithdrawError("");
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

  const openWithdrawConfirmation = () => {
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

    setIsWithdrawConfirmationOpen(true);
  };

  const withdrawAccount = async () => {
    const hasPassword = currentUser?.hasPassword === true;
    setIsWithdrawing(true);
    try {
      await appDataApi.withdraw(hasPassword ? { password: withdrawPassword } : { confirmationPhrase: withdrawConfirmation });
      await clearSessionAndRedirect();
    } catch (error) {
      setWithdrawError(accountErrorMessage(error, "회원 탈퇴를 처리하지 못했어요. 잠시 후 다시 시도해 주세요."));
      setIsWithdrawConfirmationOpen(false);
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

  const visibleSavedPolicies = uniquePoliciesBySlug(savedPolicies);
  const savedPolicyCount = Math.max(visibleSavedPolicies.length, savedSlugs.size);
  // 목록과 같은 출처(서버)로 센다. 못 불러왔을 때만 이번 세션에서 담은 것을 센다
  const appliedPolicyCount = appliedPolicyError ? addedPolicySlugs.size : appliedPolicies.length;
  const tripCount = tripError ? 0 : trips.length;
  const regions = (profile.preferredRegions ?? []).filter((region) => region.trim());
  const tags = [
    regions.length > 0 ? `관심 지역 · ${regions.join("·")}` : "관심 지역 없음",
    profile.style?.trim() || "여행 스타일 없음",
    profile.budget?.trim() || "예산 없음",
  ];
  // 활동 칸 → 그 목록으로 굴리고 초점도 옮긴다(다음 Tab 이 목록에서 이어지게)
  const scrollToSection = (id: string) => {
    const section = document.getElementById(id);
    section?.scrollIntoView({ block: "start", behavior: "smooth" });
    section?.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  };

  return (
    <section className="screen with-tabs mp-screen prototype-mypage-screen desktop-wide">
      <header className="mp-top">
        <h1>내 정보</h1>
      </header>
      <section className="mp-hero" aria-label="내 프로필 요약">
        <span aria-hidden="true" className="mp-avatar">
          {name.trim().slice(0, 1) || "여"}
        </span>
        <div className="mp-who">
          <h2 className="profile-name">{name}</h2>
          <p className="mp-mail">{currentUser?.email ?? "이메일 정보 없음"}</p>
          <ul aria-label="프로필 취향" className="mp-tags">
            {tags.map((tag) => (
              <li key={tag}>{tag}</li>
            ))}
          </ul>
        </div>
        <button className="mp-edit" disabled={!editor.ready} onClick={editor.open} type="button">
          편집
        </button>
      </section>

      <section aria-label="나의 활동 요약" className="mp-stats">
        <Link aria-label="내 일정 보기" className="mp-stat" to="/trips">
          <b>{isLoadingTrips ? "..." : tripCount}</b>
          <span>내 일정</span>
        </Link>
        <button aria-label="즐겨찾기 정책 보기" className="mp-stat" onClick={() => scrollToSection("my-favorites")} type="button">
          <b>{isLoadingSavedPolicies ? "..." : savedPolicyCount}</b>
          <span>즐겨찾기</span>
        </button>
        <button aria-label="담은 혜택 보기" className="mp-stat" onClick={() => scrollToSection("my-applied")} type="button">
          <b>{isLoadingAppliedPolicies ? "..." : appliedPolicyCount}</b>
          <span>담은 혜택</span>
        </button>
      </section>

      <div className="mp-lists">
        <section aria-labelledby="my-favorites-title" className="mp-sec" id="my-favorites">
          <div className="mp-sec-head">
            <h2 id="my-favorites-title" tabIndex={-1}>
              즐겨찾기 정책 <span>{isLoadingSavedPolicies ? "..." : savedPolicyCount}</span>
            </h2>
            <Link to="/policies">정책 찾기</Link>
          </div>
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
            <div className="mp-empty">
              <b>아직 즐겨찾기한 정책이 없어요</b>
              <span>혜택 상세에서 하트를 누르면 여기에 모여요.</span>
              <Link className="mp-empty-go" to="/policies">
                정책 보러 가기
              </Link>
            </div>
          )}
          {!isLoadingSavedPolicies && !savedPolicyError && visibleSavedPolicies.length > 0 && (
            <ul className="mp-list">
              {visibleSavedPolicies.map((policy) => (
                <MyPolicyRow
                  isRemoving={removingPolicySlug === policy.slug}
                  key={policy.slug}
                  onRemove={() => removeSavedPolicy(policy)}
                  policy={policy}
                />
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="my-applied-title" className="mp-sec" id="my-applied">
          <div className="mp-sec-head">
            <h2 id="my-applied-title" tabIndex={-1}>
              일정에 담은 혜택 <span>{isLoadingAppliedPolicies ? "..." : appliedPolicyCount}</span>
            </h2>
            {appliedPolicies.length > 0 && <Link to="/applied-policies">일정별로 보기</Link>}
          </div>
          {isLoadingAppliedPolicies && <LoadingState compact label="담은 혜택을 불러오는 중입니다" />}
          {!isLoadingAppliedPolicies && appliedPolicyError && (
            <ErrorState
              compact
              message="담은 혜택을 불러오지 못했어요."
              action={
                <Link className="btn line" to="/applied-policies">
                  일정별로 보기
                </Link>
              }
            />
          )}
          {!isLoadingAppliedPolicies && !appliedPolicyError && appliedPolicies.length === 0 && (
            <div className="mp-empty">
              <b>일정에 담은 혜택이 없어요</b>
              <span>혜택 상세의 ‘내 일정에 담기’로 담을 수 있어요.</span>
            </div>
          )}
          {!isLoadingAppliedPolicies && appliedPolicies.length > 0 && (
            <ul className="mp-list">
              {appliedPolicies.map((policy) => (
                <MyPolicyRow key={policy.slug} policy={policy} />
              ))}
            </ul>
          )}
        </section>
      </div>

      <section aria-label="설정 메뉴" className="mp-menu ds-settings-menu">
        <MenuRow icon={<CircleHelp size={20} />} label="공지사항 / FAQ" onClick={() => setInfoSheetType("faq")} />
        <MenuRow icon={<FileText size={20} />} label="이용약관" onClick={() => setInfoSheetType("terms")} />
        <MenuRow icon={<ShieldCheck size={20} />} label="개인정보처리방침" onClick={() => setInfoSheetType("privacy")} />
        <MenuRow icon={<KeyRound size={20} />} label="비밀번호 관리" onClick={() => setAccountDialogType("password")} />
        <MenuRow icon={<LogOut size={20} />} label="로그아웃" onClick={signOut} />
      </section>
      <button className="mp-quit" onClick={() => setAccountDialogType("withdrawal")} type="button">
        회원 탈퇴
      </button>

      {editor.sheet}
      {infoSheetType && <InfoSheet type={infoSheetType} onClose={() => setInfoSheetType(null)} />}
      {accountDialogType === "password" && (
        <AccountSecurityDialog
          currentPassword={currentPassword}
          error={passwordChangeError}
          hasPassword={currentUser?.hasPassword === true}
          isSubmitting={isChangingPassword}
          newPassword={newPassword}
          onChangeCurrentPassword={setCurrentPassword}
          onChangeNewPassword={setNewPassword}
          onClose={closePasswordDialog}
          onSubmit={changePassword}
        />
      )}
      {accountDialogType === "withdrawal" && !isWithdrawConfirmationOpen && (
        <AccountWithdrawalDialog
          confirmation={withdrawConfirmation}
          error={withdrawError}
          hasPassword={currentUser?.hasPassword === true}
          isSubmitting={isWithdrawing}
          password={withdrawPassword}
          onChangeConfirmation={setWithdrawConfirmation}
          onChangePassword={setWithdrawPassword}
          onClose={closeWithdrawalDialog}
          onSubmit={openWithdrawConfirmation}
        />
      )}
      {isWithdrawConfirmationOpen && (
        <WithdrawalConfirmationDialog
          isSubmitting={isWithdrawing}
          onCancel={() => !isWithdrawing && setIsWithdrawConfirmationOpen(false)}
          onConfirm={withdrawAccount}
        />
      )}
    </section>
  );
}

function MenuRow({ icon, label, onClick }: { icon: ReactNode; label: string; onClick: () => void }) {
  return (
    <button className="mp-row" onClick={onClick} type="button">
      <span aria-hidden="true" className="mp-row-icon">
        {icon}
      </span>
      <span className="mp-row-label">{label}</span>
      <ChevronRight aria-hidden="true" className="mp-row-go" size={18} />
    </button>
  );
}

/* 즐겨찾기·담은 혜택 한 줄: 혜택 그림 · 어디 · 사업 · 받는 것 · 마감(정책 탭 목록과 같은 출처). 즐겨찾기 줄만 하트로 해제 */
function MyPolicyRow({ isRemoving = false, onRemove, policy }: { isRemoving?: boolean; onRemove?: () => void; policy: Policy }) {
  const place = cityOf(policy);
  const region = policy.region === NATIONWIDE_REGION ? "전국 공통" : REGION_FULL_NAMES[policy.region] ?? policy.region;
  const head = policyListText(policy).head;
  const chip = deadlineChip(policy);
  return (
    <li className="mp-pol">
      <Link className="mp-pol-open" to={`/policies/${policy.slug}`}>
        <BenefitTile kind={benefitTypeOf(policy)} />
        <span className="mp-pol-body">
          <span className="mp-pol-where">
            <b>{place ?? region}</b>
            {place ? ` · ${policy.region}` : ""}
          </span>
          <span className="mp-pol-title">{programName(policy)}</span>
          {head && <span className="mp-pol-head">{head}</span>}
        </span>
        <span className={`mp-dday ${chip.tone}`}>{chip.text}</span>
      </Link>
      {onRemove && (
        <button aria-label={`${policy.title} 즐겨찾기 해제`} className="mp-heart" disabled={isRemoving} onClick={onRemove} type="button">
          <Heart aria-hidden="true" fill="currentColor" size={22} />
        </button>
      )}
    </li>
  );
}

function AccountSecurityDialog({
  currentPassword,
  error,
  hasPassword,
  isSubmitting,
  newPassword,
  onChangeCurrentPassword,
  onChangeNewPassword,
  onClose,
  onSubmit,
}: {
  currentPassword: string;
  error: string;
  hasPassword: boolean;
  isSubmitting: boolean;
  newPassword: string;
  onChangeCurrentPassword: (value: string) => void;
  onChangeNewPassword: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <AccountDialog labelId="account-password-title" onClose={onClose}>
      <div className="prototype-account-dialog-head">
        <div>
          <h2 id="account-password-title">비밀번호 관리</h2>
          <p>계정 보안을 위해 변경 후 다시 로그인해야 합니다.</p>
        </div>
        <button aria-label="비밀번호 관리 닫기" className="prototype-account-close" disabled={isSubmitting} onClick={onClose} type="button">×</button>
      </div>
      {hasPassword ? (
        <form className="prototype-account-dialog-body" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
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
          <div className="prototype-account-actions">
            <Button disabled={isSubmitting} onClick={onClose} variant="secondary">취소</Button>
            <Button disabled={isSubmitting} type="submit">{isSubmitting ? "변경 중입니다" : "비밀번호 변경"}</Button>
          </div>
        </form>
      ) : (
        <div className="prototype-account-dialog-body">
          <div className="prototype-account-notice oauth">
            <strong>소셜 로그인 계정입니다</strong>
            <p>이 계정은 앱 비밀번호가 없어 비밀번호 변경을 제공하지 않습니다. 비밀번호와 로그인 보안은 연결한 소셜 제공자에서 관리해 주세요.</p>
          </div>
          <Button onClick={onClose} variant="secondary">확인</Button>
        </div>
      )}
    </AccountDialog>
  );
}

function AccountWithdrawalDialog({
  confirmation,
  error,
  hasPassword,
  isSubmitting,
  password,
  onChangeConfirmation,
  onChangePassword,
  onClose,
  onSubmit,
}: {
  confirmation: string;
  error: string;
  hasPassword: boolean;
  isSubmitting: boolean;
  password: string;
  onChangeConfirmation: (value: string) => void;
  onChangePassword: (value: string) => void;
  onClose: () => void;
  onSubmit: () => void;
}) {
  return (
    <AccountDialog labelId="account-withdraw-title" onClose={onClose}>
      <div className="prototype-account-dialog-head">
        <div>
          <h2 id="account-withdraw-title">회원 탈퇴</h2>
          <p>계정을 삭제하기 전에 본인 확인이 필요합니다.</p>
        </div>
        <button aria-label="회원 탈퇴 닫기" className="prototype-account-close" disabled={isSubmitting} onClick={onClose} type="button">×</button>
      </div>
      <form className="prototype-account-dialog-body" onSubmit={(event) => { event.preventDefault(); onSubmit(); }}>
        <div className="prototype-account-notice">
          <strong>탈퇴하면 다음 내용이 적용됩니다</strong>
          <ul>
            <li>탈퇴 후 계정은 복구할 수 없습니다.</li>
            <li>같은 이메일로 다시 가입할 수 있습니다.</li>
            <li>새로 가입해도 이전 데이터는 복원되지 않습니다.</li>
          </ul>
        </div>
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
        <div className="prototype-account-actions">
          <Button disabled={isSubmitting} onClick={onClose} variant="secondary">취소</Button>
          <Button disabled={isSubmitting} type="submit" variant="danger">회원 탈퇴</Button>
        </div>
      </form>
    </AccountDialog>
  );
}

function AccountDialog({ children, labelId, onClose }: { children: ReactNode; labelId: string; onClose: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => [...(dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])') ?? [])];
    focusable()[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!document.querySelector(".prototype-account-confirm-dialog")) onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const elements = focusable();
      if (elements.length === 0) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && event.target === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && event.target === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      opener?.focus();
    };
  }, []);

  return (
    <div className="prototype-account-backdrop" onMouseDown={onClose} role="presentation">
      <section aria-labelledby={labelId} aria-modal="true" className="prototype-account-dialog" onMouseDown={(event) => event.stopPropagation()} ref={dialogRef} role="dialog">
        <div aria-hidden="true" className="prototype-account-handle" />
        {children}
      </section>
    </div>
  );
}

function WithdrawalConfirmationDialog({ isSubmitting, onCancel, onConfirm }: { isSubmitting: boolean; onCancel: () => void; onConfirm: () => void }) {
  const dialogRef = useRef<HTMLElement>(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () => [...(dialog?.querySelectorAll<HTMLElement>('button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])') ?? [])];
    focusable()[0]?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopImmediatePropagation();
        onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const elements = focusable();
      if (elements.length === 0) return;
      const first = elements[0];
      const last = elements[elements.length - 1];
      if (event.shiftKey && event.target === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && event.target === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => {
      document.removeEventListener("keydown", onKeyDown, true);
      document.body.style.overflow = previousOverflow;
      opener?.focus();
    };
  }, []);

  return (
    <div className="prototype-account-backdrop prototype-account-confirm-backdrop" onMouseDown={onCancel} role="presentation">
      <section aria-labelledby="withdraw-confirm-title" aria-modal="true" className="prototype-account-confirm-dialog" onMouseDown={(event) => event.stopPropagation()} ref={dialogRef} role="alertdialog">
        <span aria-hidden="true" className="prototype-account-danger-mark">!</span>
        <h2 id="withdraw-confirm-title">정말 탈퇴하시겠어요?</h2>
        <p>이 단계에서 탈퇴를 선택하면 계정 삭제가 시작됩니다.</p>
        <ul>
          <li>탈퇴한 계정은 복구할 수 없습니다.</li>
          <li>동일 이메일로 재가입할 수 있습니다.</li>
          <li>이전 일정과 저장 정책은 복원되지 않습니다.</li>
        </ul>
        <div className="prototype-account-actions">
          <Button disabled={isSubmitting} onClick={onCancel} variant="secondary">돌아가기</Button>
          <Button disabled={isSubmitting} onClick={onConfirm} variant="danger">{isSubmitting ? "탈퇴 처리 중입니다" : "탈퇴 확정"}</Button>
        </div>
      </section>
    </div>
  );
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
