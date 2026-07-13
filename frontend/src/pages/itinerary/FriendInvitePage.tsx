import { ChevronLeft, Send } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  appDataApi,
  type InviteLinksState,
  type InviteRole,
  type InviteState,
} from "../../api";
import { useAsyncResource } from "../../api/useAsyncResource";
import { useSession } from "../../app/session";
import {
  Button,
  ErrorState,
  IconButton,
  LoadingState,
  PageHead,
  Toast,
  TopBar,
} from "../../components/ui";
import { shareLinkWithFallback } from "../../utils/share";
import { resolveTripId } from "./_shared";

type InviteRoleOption = {
  role: InviteRole;
  label: string;
  eyebrow: string;
  body: string;
  makeLabel: string;
  copyLabel: string;
  emailLabel: string;
};

const inviteRoleOptions: InviteRoleOption[] = [
  {
    role: "viewer",
    label: "보기만 가능",
    eyebrow: "읽기 전용 링크",
    body: "이 링크를 받은 친구는 일정과 연결 정책을 확인할 수 있어요.",
    makeLabel: "보기 링크 만들기",
    copyLabel: "보기만 가능 링크 복사",
    emailLabel: "보기만 가능 email 보내기",
  },
  {
    role: "editor",
    label: "함께 편집",
    eyebrow: "편집 가능 링크",
    body: "이 링크를 받은 친구는 장소 추가·수정·이동에 참여할 수 있어요.",
    makeLabel: "편집 링크 만들기",
    copyLabel: "함께 편집 링크 복사",
    emailLabel: "함께 편집 email 보내기",
  },
];

const mergeInviteState = (
  current: InviteLinksState | null,
  base: InviteLinksState | null | undefined,
  invite: InviteState,
): InviteLinksState => ({
  tripId: invite.tripId,
  viewer:
    invite.role === "viewer"
      ? invite
      : (current?.viewer ?? base?.viewer ?? null),
  editor:
    invite.role === "editor"
      ? invite
      : (current?.editor ?? base?.editor ?? null),
});

export function FriendInvitePage() {
  const { invited, sendInvite } = useSession();
  const [searchParams] = useSearchParams();
  const requestedTripId = searchParams.get("tripId");
  const [activeTripId, setActiveTripId] = useState(requestedTripId ?? "");
  const {
    data: trip,
    error: tripError,
    isLoading: tripLoading,
  } = useAsyncResource(async () => {
    const resolvedTripId = await resolveTripId(requestedTripId);
    setActiveTripId(resolvedTripId ?? "");
    if (!resolvedTripId) throw new Error("Trip not found");
    return appDataApi.getTrip(resolvedTripId);
  }, [requestedTripId]);
  const {
    data: inviteState,
    error: inviteError,
    isLoading: inviteLoading,
  } = useAsyncResource(async () => {
    const resolvedTripId = await resolveTripId(requestedTripId);
    if (!resolvedTripId) throw new Error("Trip not found");
    return appDataApi.getInviteState(resolvedTripId);
  }, [requestedTripId]);
  const [sentInviteState, setSentInviteState] =
    useState<InviteLinksState | null>(null);
  const [copiedRole, setCopiedRole] = useState<InviteRole | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [inviteEmails, setInviteEmails] = useState<Record<InviteRole, string>>({
    viewer: "",
    editor: "",
  });
  const [sendingEmailRole, setSendingEmailRole] = useState<InviteRole | null>(
    null,
  );
  const effectiveInviteState = sentInviteState ?? inviteState;
  const detailPath = activeTripId ? `/trips/${activeTripId}` : "/trips";
  const title = trip?.title ?? "제주 3일 여행";
  const canManageInvite =
    trip?.currentUserRole === "owner" || trip?.currentUserRole === "editor";

  const updateRoleInvite = (invite: InviteState) => {
    setSentInviteState((current) =>
      mergeInviteState(current, inviteState, invite),
    );
  };

  const shareInviteLink = async (option: InviteRoleOption) => {
    const roleInvite = effectiveInviteState?.[option.role];
    const inviteUrl = roleInvite?.inviteUrl ?? "";
    if (!inviteUrl) return;
    try {
      const method = await shareLinkWithFallback({
        title: `${title} ${option.label} 초대 링크`,
        text: `${title} 일정을 ${option.label} 권한으로 공유해 보세요.`,
        url: inviteUrl,
      });
      setCopiedRole(option.role);
      setNotice(
        method === "share"
          ? `${option.label} 링크를 공유했어요.`
          : `${option.label} 링크를 복사했어요.`,
      );
    } catch {
      setCopiedRole(option.role);
      setNotice("초대 링크를 공유하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  const prepareInviteLink = async (role: InviteRole) => {
    const tripId = activeTripId || effectiveInviteState?.tripId;
    if (!tripId) return;
    const nextInviteState = await appDataApi.confirmInviteSent(tripId, role);
    updateRoleInvite(nextInviteState);
    sendInvite();
    setNotice(
      role === "viewer"
        ? "보기만 가능 링크가 준비됐어요."
        : "함께 편집 링크가 준비됐어요.",
    );
  };

  const sendFriendInviteEmail = async (role: InviteRole) => {
    const tripId = activeTripId || effectiveInviteState?.tripId;
    const email = inviteEmails[role].trim();
    if (!tripId || !email || sendingEmailRole) return;
    setSendingEmailRole(role);
    try {
      const result = await appDataApi.sendInviteEmail(tripId, { email, role });
      updateRoleInvite(result.invite);
      if (result.deliveryStatus === "sent") {
        setNotice(
          "초대 email을 보냈어요. 친구는 로그인 또는 회원가입 후 수락할 수 있어요.",
        );
      } else if (result.deliveryStatus === "notConfigured") {
        setNotice(
          "email 발송 설정이 아직 없어요. 해당 권한 링크를 복사해 직접 보내 주세요.",
        );
      } else {
        setNotice(
          "email을 보내지 못했어요. 해당 권한 링크를 복사해 직접 보내 주세요.",
        );
      }
    } catch {
      setNotice(
        "email 초대 요청을 처리하지 못했어요. 링크 복사로 먼저 공유해 주세요.",
      );
    } finally {
      setSendingEmailRole(null);
    }
  };

  return (
    <section className="screen">
      <TopBar
        title="친구 초대"
        left={
          <IconButton label="일정 상세" to={detailPath}>
            <ChevronLeft size={20} />
          </IconButton>
        }
      />
      <div className="content stack padded">
        {(tripLoading || inviteLoading) && (
          <LoadingState label="초대 정보를 불러오는 중입니다" />
        )}
        {(tripError || inviteError) && (
          <ErrorState
            message={tripError ?? inviteError ?? "초대 정보를 찾지 못했어요."}
          />
        )}
        {trip && !canManageInvite && (
          <ErrorState message="친구 초대는 일정 owner/editor 멤버만 관리할 수 있어요. 일정 상세로 돌아가 현재 권한을 확인해 주세요." />
        )}
        {canManageInvite && (
          <>
            <div className="card invite-permission-overview">
              <div className="card-body stack">
                <PageHead
                  eyebrow="권한별 초대 링크"
                  title={`${title} 초대 링크를 권한별로 관리하세요`}
                  body="보기만 가능과 함께 편집 링크는 서로 다른 URL이에요. 한 번 공유한 링크의 권한은 다른 링크를 만들어도 바뀌지 않습니다."
                />
              </div>
            </div>
            <div className="invite-role-card-grid">
              {inviteRoleOptions.map((option) => {
                const roleInvite = effectiveInviteState?.[option.role] ?? null;
                const emailValue = inviteEmails[option.role];
                const copied = copiedRole === option.role;
                return (
                  <article className="card invite-role-card" key={option.role}>
                    <div className="card-body stack tight">
                      <div className="invite-role-card-head">
                        <div>
                          <span className="invite-role-eyebrow">
                            {option.eyebrow}
                          </span>
                          <h3>{option.label}</h3>
                        </div>
                        <span className={`invite-role-badge ${option.role}`}>
                          {option.role}
                        </span>
                      </div>
                      <p className="meta">{option.body}</p>
                      <div className="invite-link role-link">
                        <span>
                          {roleInvite?.inviteUrl ??
                            `${option.label} 링크를 만들면 여기에 표시돼요.`}
                        </span>
                        <button
                          className="btn sm ghost"
                          disabled={!roleInvite?.inviteUrl}
                          onClick={() => shareInviteLink(option)}
                          type="button"
                        >
                          {copied ? "복사됨" : option.copyLabel}
                        </button>
                      </div>
                      <div className="invite-role-actions">
                        <button
                          className="btn sm line"
                          onClick={() => prepareInviteLink(option.role)}
                          type="button"
                        >
                          {invited || roleInvite?.invited
                            ? `${option.label} 링크 준비 완료`
                            : option.makeLabel}
                        </button>
                      </div>
                      <label className="field invite-email-field">
                        <span>{option.label} 친구 email</span>
                        <input
                          inputMode="email"
                          onChange={(event) =>
                            setInviteEmails((current) => ({
                              ...current,
                              [option.role]: event.target.value,
                            }))
                          }
                          placeholder="friend@example.com"
                          type="email"
                          value={emailValue}
                        />
                      </label>
                      <Button
                        disabled={
                          !emailValue.trim() || sendingEmailRole === option.role
                        }
                        full
                        onClick={() => sendFriendInviteEmail(option.role)}
                      >
                        <Send size={18} />
                        {sendingEmailRole === option.role
                          ? "email 보내는 중"
                          : option.emailLabel}
                      </Button>
                    </div>
                  </article>
                );
              })}
            </div>
            {notice && <Toast>{notice}</Toast>}
          </>
        )}
      </div>
    </section>
  );
}
