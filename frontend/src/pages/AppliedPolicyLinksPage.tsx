import { ChevronLeft } from "lucide-react";
import { Link } from "react-router-dom";
import { appDataApi, type AppliedPolicyLink, type AppliedPolicyLinkedTrip } from "../api";
import { useAsyncResource } from "../api/useAsyncResource";
import { EmptyState, ErrorState, IconButton, LinkButton, LoadingState } from "../components/ui";
import { getPolicyMoodIcon, getPolicyMoodTone } from "../data/displayConfig";

function formatTripDates(trip: AppliedPolicyLinkedTrip) {
  if (!trip.startDate || !trip.endDate) return "일정 날짜 미정";
  if (trip.startDate === trip.endDate) return trip.startDate;
  return `${trip.startDate} - ${trip.endDate}`;
}


function AppliedPolicyCard({ item }: { item: AppliedPolicyLink }) {
  const { policy, linkedTrips } = item;

  return (
    <article className="prototype-applied-policy-card">
      <div className="prototype-applied-policy-main">
        <div className={`prototype-applied-policy-label policy-list-icon ${getPolicyMoodTone(policy)}`} aria-hidden="true">
          {getPolicyMoodIcon(policy)}
        </div>
        <div className="prototype-applied-policy-copy">
          <Link className="prototype-applied-policy-title" to={`/policies/${encodeURIComponent(policy.slug)}`}>
            {policy.title}
          </Link>
          <p>{policy.summary || `${policy.region}에서 사용할 수 있는 정책입니다.`}</p>
          <div className="prototype-applied-policy-meta">
            <span>{policy.region}</span>
            <span>{policy.amount || "혜택 확인 필요"}</span>
          </div>
        </div>
      </div>

      <div className="prototype-applied-trip-list" aria-label={`${policy.title} 연결 일정`}>
        <strong>연결된 일정</strong>
        {linkedTrips.map((trip) => (
          <Link className="prototype-applied-trip-link" key={trip.id} to={`/trips/${trip.id}`}>
            <span>
              <b>{trip.title}</b>
              <small>{formatTripDates(trip)}</small>
            </span>
            <em>{trip.region || "지역 미정"}</em>
          </Link>
        ))}
      </div>
    </article>
  );
}

export function AppliedPolicyLinksPage() {
  const { data: appliedPolicyLinks, error, isLoading } = useAsyncResource(() => appDataApi.listAppliedPolicyLinks(), []);
  const items = appliedPolicyLinks ?? [];
  const linkedTripCount = items.reduce((total, item) => total + item.linkedTrips.length, 0);

  return (
    <section className="screen with-tabs prototype-applied-policies-screen">
      <div className="top-bar">
        <IconButton label="마이페이지로 돌아가기" to="/mypage">
          <ChevronLeft size={22} />
        </IconButton>
        <h1>신청 정책</h1>
        <div />
      </div>

      <div className="content stack padded prototype-applied-policies-content">
        <section className="prototype-applied-policy-hero" aria-label="신청 정책 요약">
          <span>내 일정에 담긴 정책</span>
          <h2>일정과 연결한 정책을 모아봤어요</h2>
          <p>정책을 눌러 상세 조건을 확인하고, 연결된 일정을 눌러 바로 이동할 수 있습니다.</p>
          <div className="prototype-applied-policy-summary">
            <strong>{items.length}</strong>
            <span>정책</span>
            <strong>{linkedTripCount}</strong>
            <span>연결 일정</span>
          </div>
        </section>

        {isLoading && <LoadingState label="신청 정책을 불러오는 중입니다" />}
        {!isLoading && error && <ErrorState message={error} action={<LinkButton to="/mypage" variant="line">마이페이지로 돌아가기</LinkButton>} />}
        {!isLoading && !error && items.length === 0 && (
          <EmptyState
            eyebrow="신청 정책"
            title="아직 일정에 담긴 정책이 없어요"
            body="정책 상세에서 내 일정에 담으면 이곳에서 일정별로 확인할 수 있습니다."
            action={<LinkButton to="/policies" variant="primary">정책 찾아보기</LinkButton>}
          />
        )}
        {!isLoading && !error && items.length > 0 && (
          <div className="prototype-applied-policy-list">
            {items.map((item) => (
              <AppliedPolicyCard item={item} key={item.policy.slug} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
