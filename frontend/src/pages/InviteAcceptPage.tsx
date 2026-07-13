import { useEffect, useRef, useState } from "react";
import { ChevronLeft } from "lucide-react";
import { useParams } from "react-router-dom";
import { appDataApi, InviteState } from "../api";
import { useSession } from "../app/session";
import { ErrorState, IconButton, LinkButton, LoadingState, PageHead, TopBar } from "../components/ui";

type AcceptStatus = "loading" | "success" | "error";

export function InviteAcceptPage() {
  const { inviteToken = "" } = useParams();
  const { currentUser, isSessionBootstrapping } = useSession();
  const [status, setStatus] = useState<AcceptStatus>("loading");
  const [invite, setInvite] = useState<InviteState | null>(null);
  const submittedToken = useRef<string | null>(null);
  const redirectPath = `/invites/${encodeURIComponent(inviteToken)}/accept`;
  const loginPath = `/login?redirect=${encodeURIComponent(redirectPath)}`;
  const signupPath = `/signup?redirect=${encodeURIComponent(redirectPath)}`;

  useEffect(() => {
    if (!inviteToken) {
      setStatus("error");
      return;
    }
    if (isSessionBootstrapping) {
      setStatus("loading");
      return;
    }
    if (!currentUser) {
      setStatus("error");
      submittedToken.current = null;
      return;
    }
    if (submittedToken.current === inviteToken) return;

    submittedToken.current = inviteToken;
    setStatus("loading");
    setInvite(null);

    appDataApi
      .acceptInvite(inviteToken)
      .then((acceptedInvite) => {
        setInvite(acceptedInvite);
        setStatus("success");
      })
      .catch(() => {
        setStatus("error");
      });
  }, [currentUser, inviteToken, isSessionBootstrapping]);

  return (
    <section className="screen white with-tabs">
      <TopBar
        title="초대 수락"
        left={
          <IconButton label="홈으로" to="/home">
            <ChevronLeft size={20} />
          </IconButton>
        }
      />
      <div className="content">
        <PageHead
          eyebrow="친구 초대"
          title="함께 준비할 여행에 참여하세요"
          body="초대를 수락하면 친구의 여행 일정에서 혜택과 추천 코스를 함께 확인할 수 있어요."
        />

        {status === "loading" && <LoadingState label="초대 정보를 확인하는 중입니다" />}

        {status === "success" && invite && (
          <div className="card card-body">
            <span className="tag primary">수락 완료</span>
            <h3>{invite.alreadyMember ? "이미 참여 중인 일정입니다" : "초대를 수락했어요"}</h3>
            <p>{invite.alreadyMember ? "기존 권한은 그대로 유지돼요. 일정 상세에서 바로 이어서 확인할 수 있습니다." : "이제 일정 상세에서 여행 코스와 연결된 혜택을 함께 확인할 수 있어요."}</p>
            {invite.acceptedAt && <p className="meta">수락 시각 {new Date(invite.acceptedAt).toLocaleString("ko-KR")}</p>}
            <div className="sheet-actions">
              <LinkButton to={`/trips/${invite.tripId}`} full>
                일정 보기
              </LinkButton>
              <LinkButton to="/home" variant="line" full>
                홈으로
              </LinkButton>
            </div>
          </div>
        )}

        {status === "error" && !currentUser && inviteToken && (
          <div className="card card-body">
            <span className="tag primary">일정 초대</span>
            <h3>트래블헌터 일정 초대입니다</h3>
            <p>일정 상세 내용은 로그인 또는 회원가입 후 초대를 수락한 뒤 확인할 수 있습니다.</p>
            <p className="meta">초대가 만료됐으면 초대한 사람에게 새 초대 링크를 요청하세요.</p>
            <div className="sheet-actions">
              <LinkButton to={loginPath} full>
                로그인하고 수락하기
              </LinkButton>
              <LinkButton to={signupPath} variant="line" full>
                회원가입하고 수락하기
              </LinkButton>
            </div>
          </div>
        )}

        {status === "error" && (currentUser || !inviteToken) && (
          <>
            <ErrorState message="초대 링크를 찾을 수 없어요. 링크가 만료되었거나 다시 발급이 필요해요. 초대한 친구에게 새 초대 링크를 요청해 주세요." />
            <div className="sheet-actions">
              <LinkButton to="/trips" full>
                내 일정 보기
              </LinkButton>
              <LinkButton to="/home" variant="line" full>
                홈으로
              </LinkButton>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
