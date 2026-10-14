import { ChevronLeft } from "lucide-react";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { IconButton, TopBar } from "../../components/ui";
import { FriendInvitePanel } from "./FriendInvitePanel";

export function FriendInvitePage() {
  const [searchParams] = useSearchParams();
  const requestedTripId = searchParams.get("tripId");
  const [activeTripId, setActiveTripId] = useState(requestedTripId ?? "");
  const detailPath = activeTripId ? `/trips/${activeTripId}` : "/trips";

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
        {/* 일정이 바뀌면 새로 그린다 - 앞 일정에서 만든 링크가 남지 않게 */}
        <FriendInvitePanel
          key={requestedTripId ?? ""}
          requestedTripId={requestedTripId}
          onResolvedTripId={setActiveTripId}
        />
      </div>
    </section>
  );
}
