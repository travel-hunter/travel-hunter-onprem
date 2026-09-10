import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { appDataApi, type InviteState } from "../../api";
import { useAsyncResource } from "../../api/useAsyncResource";
import { useSession } from "../../app/session";
import {
  Button,
  ErrorState,
  LoadingState,
  PageHead,
  Toast,
} from "../../components/ui";
import { shareLinkWithFallback } from "../../utils/share";
import { resolveTripId } from "./_shared";

type FriendInvitePanelProps = {
  /* 페이지는 쿼리스트링에서, 일정 상세 시트는 열려 있는 일정에서 넘긴다. */
  requestedTripId: string | null;
  /* 페이지 상단 뒤로가기가 어느 일정으로 돌아갈지 알아야 한다. */
  onResolvedTripId?: (tripId: string) => void;
  /* 시트는 링크를 보여 주려고 여는 화면이다. 열자마자 링크가 있어야 한다.
     전용 페이지는 그냥 둘러볼 수도 있으므로 기존대로 직접 누르게 둔다. */
  autoPrepareLink?: boolean;
};

/* 초대 화면의 알맹이. 전용 페이지와 일정 상세 시트가 같이 쓴다.
   둘이 갈라지면 링크 만들기와 email 초대가 화면마다 달라진다. */
export function FriendInvitePanel({
  requestedTripId,
  onResolvedTripId,
  autoPrepareLink = false,
}: FriendInvitePanelProps) {
  const { invited, sendInvite } = useSession();
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
  const [sentInviteState, setSentInviteState] = useState<InviteState | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const effectiveInviteState = sentInviteState ?? inviteState;
  const title = trip?.title ?? "제주 3일 여행";
  const canManageInvite =
    trip?.currentUserRole === "owner" || trip?.currentUserRole === "editor";

  const shareInviteLink = async () => {
    const inviteUrl = effectiveInviteState?.inviteUrl ?? "";
    if (!inviteUrl) return;
    try {
      const method = await shareLinkWithFallback({
        title: `${title} 함께 편집 초대 링크`,
        text: `${title} 일정을 함께 편집할 수 있도록 공유해 보세요.`,
        url: inviteUrl,
      });
      setCopied(true);
      setNotice(
        method === "share"
          ? "함께 편집 링크를 공유했어요."
          : "함께 편집 링크를 복사했어요.",
      );
    } catch {
      setCopied(true);
      setNotice("초대 링크를 공유하지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  /* silent 는 자동 준비용이다. 사용자가 누르지 않았는데 "준비됐어요" 를 띄우면 군더더기다. */
  const prepareInviteLink = async (options?: { silent?: boolean }) => {
    const tripId = activeTripId || effectiveInviteState?.tripId;
    if (!tripId) return;
    try {
      const nextInviteState = await appDataApi.confirmInviteSent(tripId);
      setSentInviteState(nextInviteState);
      sendInvite();
      if (!options?.silent) setNotice("함께 편집 링크가 준비됐어요.");
    } catch {
      setNotice("초대 링크를 만들지 못했어요. 잠시 후 다시 시도해 주세요.");
    }
  };

  const sendFriendInviteEmail = async () => {
    const tripId = activeTripId || effectiveInviteState?.tripId;
    const email = inviteEmail.trim();
    if (!tripId || !email || sendingEmail) return;
    setSendingEmail(true);
    try {
      const result = await appDataApi.sendInviteEmail(tripId, { email });
      setSentInviteState(result.invite);
      if (result.deliveryStatus === "sent") {
        setNotice(
          "초대 email을 보냈어요. 친구는 로그인 또는 회원가입 후 함께 편집할 수 있어요.",
        );
      } else if (result.deliveryStatus === "notConfigured") {
        setNotice(
          "email 발송 설정이 아직 없어요. 초대 링크를 복사해 직접 보내 주세요.",
        );
      } else {
        setNotice(
          "email을 보내지 못했어요. 초대 링크를 복사해 직접 보내 주세요.",
        );
      }
    } catch {
      setNotice(
        "email 초대 요청을 처리하지 못했어요. 링크 복사로 먼저 공유해 주세요.",
      );
    } finally {
      setSendingEmail(false);
    }
  };

  /* 링크는 한 번만 만든다. 실패해도 다시 두드리지 않는다. */
  const autoPreparedRef = useRef(false);
  useEffect(() => {
    if (!autoPrepareLink || autoPreparedRef.current) return;
    if (!canManageInvite || tripLoading || inviteLoading) return;
    if (effectiveInviteState?.inviteUrl) return;
    autoPreparedRef.current = true;
    void prepareInviteLink({ silent: true });
    // prepareInviteLink 는 매 렌더 새로 만들어진다. 위 ref 가 재실행을 막는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    autoPrepareLink,
    canManageInvite,
    effectiveInviteState?.inviteUrl,
    inviteLoading,
    tripLoading,
  ]);

  useEffect(() => {
    if (activeTripId) onResolvedTripId?.(activeTripId);
    // onResolvedTripId 는 매 렌더 새로 만들어질 수 있어 의존성에서 뺀다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTripId]);

  return (
    <>
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
                eyebrow="초대 링크"
                title={`${title}에 함께할 친구를 초대하세요`}
                body="링크를 보내면 친구가 로그인 후 일정에 참여할 수 있어요."
              />
            </div>
          </div>
          <div className="invite-role-card-grid">
            <article className="card invite-role-card">
              <div className="card-body stack tight">
                <div className="invite-role-card-head">
                  <div>
                    <span className="invite-role-eyebrow">
                      편집 가능 링크
                    </span>
                    <h3>함께 편집 링크</h3>
                  </div>
                  <span className="invite-role-badge editor">editor</span>
                </div>
                <div className="invite-link role-link">
                  <span>
                    {effectiveInviteState?.inviteUrl ??
                      "편집 링크를 만들면 여기에 표시돼요."}
                  </span>
                  <button
                    className="btn sm ghost"
                    disabled={!effectiveInviteState?.inviteUrl}
                    onClick={shareInviteLink}
                    type="button"
                  >
                    {copied ? "복사됨" : "함께 편집 링크 복사"}
                  </button>
                </div>
                <div className="invite-role-actions">
                  <button
                    className="btn sm line"
                    onClick={() => prepareInviteLink()}
                    type="button"
                  >
                    {invited || effectiveInviteState?.invited
                      ? "함께 편집 링크 준비 완료"
                      : "편집 링크 만들기"}
                  </button>
                </div>
                <label className="field invite-email-field">
                  <span>친구 email</span>
                  <input
                    inputMode="email"
                    onChange={(event) => setInviteEmail(event.target.value)}
                    placeholder="friend@example.com"
                    type="email"
                    value={inviteEmail}
                  />
                </label>
                <Button
                  disabled={!inviteEmail.trim() || sendingEmail}
                  full
                  onClick={sendFriendInviteEmail}
                >
                  <Send size={18} />
                  {sendingEmail ? "email 보내는 중" : "email 초대 보내기"}
                </Button>
              </div>
            </article>
          </div>
          {notice && <Toast>{notice}</Toast>}
        </>
      )}
    </>
  );
}
