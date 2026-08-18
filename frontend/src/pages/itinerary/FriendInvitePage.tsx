import { ChevronLeft, Send } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { appDataApi, type InviteState } from "../../api";
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
  const [sentInviteState, setSentInviteState] = useState<InviteState | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [inviteEmail, setInviteEmail] = useState("");
  const [sendingEmail, setSendingEmail] = useState(false);
  const effectiveInviteState = sentInviteState ?? inviteState;
  const detailPath = activeTripId ? `/trips/${activeTripId}` : "/trips";
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

  const prepareInviteLink = async () => {
    const tripId = activeTripId || effectiveInviteState?.tripId;
    if (!tripId) return;
    const nextInviteState = await appDataApi.confirmInviteSent(tripId);
    setSentInviteState(nextInviteState);
    sendInvite();
    setNotice("함께 편집 링크가 준비됐어요.");
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
                      onClick={prepareInviteLink}
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
      </div>
    </section>
  );
}
