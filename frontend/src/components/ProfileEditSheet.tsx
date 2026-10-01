import { useEffect, useRef, useState, type ReactNode } from "react";
import { X } from "lucide-react";
import { appDataApi, type Profile } from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { useSession } from "../app/session";
import "../styles/account.css";

const MAX_REGIONS = 3; // 프로필 완성 기준(관심 지역 1~3곳)과 같다

/* 프로필 편집 창(시안 v49): 닉네임 · 관심 지역 · 여행 스타일 · 예산. 내 정보 '편집'과 홈 '관심 지역 바꾸기'가 같이 쓴다.
   폰은 아래에서 올라오는 시트, 넓은 화면은 가운데 창(account.css). */
export function useProfileEditor(): { open: () => void; ready: boolean; sheet: ReactNode } {
  const { currentUser, isSessionBootstrapping, profile, saveNickname, saveProfile } = useSession();
  const { data: options } = useAsyncResource(() => appDataApi.getProfileOptions(), []);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [nickname, setNickname] = useState("");
  const [nicknameError, setNicknameError] = useState("");
  const [error, setError] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [isSuggesting, setIsSuggesting] = useState(false);

  /* 새로 띄운 화면은 서버 프로필을 한 번 더 받는다(session.tsx applyAuth). 그 전에 열면 빈 자리값으로 초안이 잡혀
     저장할 때 관심 지역·스타일·예산이 지워진다 - 다 받을 때까지는 열지 않는다(ProfileSetupPage 와 같은 이유) */
  const ready = !isSessionBootstrapping;
  const open = () => {
    if (!ready) return;
    setDraft(profile);
    setNickname(currentUser?.nickname ?? "여행자");
    setNicknameError("");
    setError("");
  };
  const close = () => {
    if (!isSaving) setDraft(null);
  };

  const suggest = async () => {
    setNicknameError("");
    setIsSuggesting(true);
    try {
      setNickname((await appDataApi.getNicknameSuggestion()).nickname);
    } catch {
      setNicknameError("닉네임을 추천하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSuggesting(false);
    }
  };

  const save = async () => {
    if (!draft) return;
    const trimmed = nickname.trim();
    setNicknameError("");
    setError("");
    if (trimmed.length < 2 || trimmed.length > 20) {
      setNicknameError("닉네임은 2자 이상 20자 이하로 입력해 주세요.");
      return;
    }
    setIsSaving(true);
    if (trimmed !== (currentUser?.nickname ?? "").trim()) {
      try {
        await saveNickname(trimmed);
      } catch {
        setNicknameError("닉네임을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
        setIsSaving(false);
        return;
      }
    }
    try {
      await saveProfile(draft);
      setDraft(null);
    } catch {
      setError("프로필을 저장하지 못했어요. 잠시 후 다시 시도해 주세요.");
    } finally {
      setIsSaving(false);
    }
  };

  const sheet = draft ? (
    <ProfileEditSheet
      draft={draft}
      error={error}
      isSaving={isSaving}
      isSuggesting={isSuggesting}
      nickname={nickname}
      nicknameError={nicknameError}
      regions={options?.regions ?? []}
      styles={options?.travelStyles ?? []}
      budgets={options?.budgets ?? []}
      onCancel={close}
      onChange={setDraft}
      onNicknameChange={setNickname}
      onSave={save}
      onSuggest={suggest}
    />
  ) : null;
  return { open, ready, sheet };
}

function ProfileEditSheet({
  budgets,
  draft,
  error,
  isSaving,
  isSuggesting,
  nickname,
  nicknameError,
  regions,
  styles,
  onCancel,
  onChange,
  onNicknameChange,
  onSave,
  onSuggest,
}: {
  budgets: readonly string[];
  draft: Profile;
  error: string;
  isSaving: boolean;
  isSuggesting: boolean;
  nickname: string;
  nicknameError: string;
  regions: readonly string[];
  styles: readonly string[];
  onCancel: () => void;
  onChange: (draft: Profile) => void;
  onNicknameChange: (nickname: string) => void;
  onSave: () => void;
  onSuggest: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;
  useEffect(() => {
    const opener = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancelRef.current();
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      opener?.focus();
    };
  }, []);

  const picked = draft.preferredRegions ?? [];
  const toggleRegion = (region: string) => {
    const next = picked.includes(region) ? picked.filter((item) => item !== region) : [...picked, region];
    onChange({ ...draft, preferredRegions: next.length > 0 ? next : null });
  };

  return (
    <div className="acct-sheet-backdrop" role="presentation" onMouseDown={onCancel}>
      <section
        aria-labelledby="profile-editor-title"
        aria-modal="true"
        className="acct-sheet"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
      >
        <div className="acct-sheet-head">
          <div>
            <h2 id="profile-editor-title">프로필 편집</h2>
            <p>관심 지역을 고르면 홈에 그 지역 혜택이 먼저 보여요</p>
          </div>
          <button aria-label="닫기" className="acct-icon-btn" disabled={isSaving} onClick={onCancel} ref={closeRef} type="button">
            <X aria-hidden="true" size={22} />
          </button>
        </div>
        <div className="pe-field">
          <label htmlFor="profile-nickname">닉네임</label>
          <div className="pe-nick">
            <input
              autoComplete="nickname"
              disabled={isSaving}
              id="profile-nickname"
              maxLength={20}
              name="nickname"
              onChange={(event) => onNicknameChange(event.target.value)}
              type="text"
              value={nickname}
            />
            <button className="pe-suggest" disabled={isSaving || isSuggesting} onClick={onSuggest} type="button">
              추천 받기
            </button>
          </div>
          {nicknameError && (
            <p className="form-error" role="alert">
              {nicknameError}
            </p>
          )}
        </div>
        <fieldset className="pe-group">
          <legend>
            관심 지역<i>최대 {MAX_REGIONS}곳</i>
          </legend>
          <div className="pe-chips">
            {regions.map((region) => {
              const on = picked.includes(region);
              return (
                <button
                  aria-pressed={on}
                  className="pe-chip"
                  disabled={isSaving || (!on && picked.length >= MAX_REGIONS)}
                  key={region}
                  onClick={() => toggleRegion(region)}
                  type="button"
                >
                  {region}
                </button>
              );
            })}
          </div>
        </fieldset>
        <ChoiceGroup label="여행 스타일" selected={draft.style} values={styles} disabled={isSaving} onSelect={(style) => onChange({ ...draft, style })} />
        <ChoiceGroup label="예산" selected={draft.budget} values={budgets} disabled={isSaving} onSelect={(budget) => onChange({ ...draft, budget })} />
        {error && <p className="form-error">{error}</p>}
        <button className="acct-main" disabled={isSaving} onClick={onSave} type="button">
          {isSaving ? "저장 중입니다" : "저장"}
        </button>
      </section>
    </div>
  );
}

function ChoiceGroup({
  disabled,
  label,
  onSelect,
  selected,
  values,
}: {
  disabled: boolean;
  label: string;
  onSelect: (value: string) => void;
  selected: string | null;
  values: readonly string[];
}) {
  return (
    <fieldset className="pe-group">
      <legend>{label}</legend>
      <div className="pe-chips">
        {values.map((value) => (
          <button aria-pressed={selected === value} className="pe-chip" disabled={disabled} key={value} onClick={() => onSelect(value)} type="button">
            {value}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
