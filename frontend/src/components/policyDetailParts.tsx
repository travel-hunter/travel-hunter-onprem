import { Check, ExternalLink } from "lucide-react";
import { Fragment, type CSSProperties, type ReactNode } from "react";
import type { Policy } from "../api";
import { getPolicyPhoto, getPolicyVisual } from "../data/displayConfig";
import {
  daysUntilPolicyDeadline,
  formatDottedPolicyDeadline,
  formatPolicyDeadlineTag,
  isDigitalTourismResidentCardPolicy,
  isSafePolicyDeadline,
} from "../utils";
import { getKstDateInputValue } from "../utils/dateDefaults";
import {
  policyHowTo,
  policyPlaceAndProgram,
  policyTimeline,
  won,
  type PolicyDetailText,
} from "../utils/policyDetailText";
import { BENEFIT_TYPES, BenefitTile, type BenefitType } from "./benefitTile";
import { REGION_PHOTOS } from "./map/regionPhotos";
import { PolicyHeroPhoto } from "./policyPhoto";
import "../styles/policy-detail.css";

/* 정책 상세(시안 v27)를 이루는 칸들. 상태·동작은 PolicyDetailPage 가 들고, 여기는 그리기만 한다. */

/* 주민증 혜택은 마감일이 있어도 '상시 발급'이다(앱 규칙) - 끝난 것으로 보지 않는다 */
export function isPolicyEnded(policy: Pick<Policy, "deadline" | "title" | "officialUrl">): boolean {
  if (isDigitalTourismResidentCardPolicy(policy)) return false;
  const days = daysUntilPolicyDeadline(policy.deadline);
  return days !== null && days < 0;
}

function External() {
  return <ExternalLink aria-hidden="true" size={16} strokeWidth={2} />;
}

function OfficialMissing({ what, officialUrl }: { what: string; officialUrl: string | null }) {
  return (
    <p className="policy-detail-miss">
      {what} 공식 안내에서 확인해 주세요.{" "}
      {officialUrl && (
        <a href={officialUrl} rel="noopener noreferrer" target="_blank">
          공식 안내 열기
        </a>
      )}
    </p>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: ReactNode }) {
  return (
    <section className="policy-detail-section" aria-labelledby={id}>
      <h2 id={id}>{title}</h2>
      {children}
    </section>
  );
}

function List({ items, className }: { items: string[]; className?: string }) {
  return (
    <ul className={className ? `policy-detail-list ${className}` : "policy-detail-list"}>
      {items.map((item, index) => (
        <li key={`${index}-${item}`}>{item}</li>
      ))}
    </ul>
  );
}

/* 머리 사진: 정책 사진 → 없거나 깨지면 그 시도 사진 → 전국 공통은 혜택 형태 그림 칸 */
export function PolicyDetailHero({ policy, kind, children }: { policy: Policy; kind: BenefitType; children: ReactNode }) {
  const photo = getPolicyPhoto(policy);
  const regionPhoto = REGION_PHOTOS[policy.region];
  const visual = getPolicyVisual(policy);
  const style: CSSProperties = regionPhoto
    ? { backgroundImage: `url(${regionPhoto})` }
    : { background: `linear-gradient(145deg, ${visual.from}, ${visual.to})` };
  return (
    <div className="hero policy-detail-hero" style={style}>
      {!regionPhoto && <BenefitTile kind={kind} />}
      {photo && <PolicyHeroPhoto photo={photo} />}
      {children}
    </div>
  );
}

export function PolicyDetailHead({ policy, kind }: { policy: Policy; kind: BenefitType }) {
  const { place, program } = policyPlaceAndProgram(policy.title);
  const ended = isPolicyEnded(policy);
  const days = daysUntilPolicyDeadline(policy.deadline);
  const where = place ? (
    <>
      <b>{place}</b>
      {place !== policy.region && ` · ${policy.region}`}
    </>
  ) : (
    <b>{policy.region === "전국" ? "전국 공통" : policy.region}</b>
  );
  return (
    <>
      <header className="policy-detail-head">
        <div className="policy-detail-eyebrow">
          <BenefitTile kind={kind} size="sm" />
          <span>{where}</span>
        </div>
        <h1>{program}</h1>
        {policy.org && <p className="policy-detail-org">{policy.org} 주관</p>}
        <div className="policy-detail-chips">
          <span className="policy-detail-kind">{BENEFIT_TYPES[kind].label}</span>
          {/* 마감일이 없으면 아래 '기간' 칸이 같은 말을 한다 - 한 번만 */}
          {isSafePolicyDeadline(policy.deadline) && !isDigitalTourismResidentCardPolicy(policy) && (
            <span className={`policy-detail-dday${days !== null && days <= 7 ? " urgent" : ""}`}>
              {formatPolicyDeadlineTag(policy)}
            </span>
          )}
        </div>
      </header>
      {ended && (
        <div className="policy-detail-ended" role="note">
          <b>모집이 끝난 혜택이에요</b>
          <span>{formatDottedPolicyDeadline(policy.deadline)}에 마감됐어요. 다음 모집은 공식 안내에서 확인해 주세요.</span>
        </div>
      )}
    </>
  );
}

export function PolicyDetailFacts({
  policy,
  text,
  kind,
  amountLabel,
}: {
  policy: Policy;
  text: PolicyDetailText;
  kind: BenefitType;
  amountLabel: string;
}) {
  const today = getKstDateInputValue();
  const start = isSafePolicyDeadline(policy.startDate) ? policy.startDate : null;
  const when = isPolicyEnded(policy)
    ? "끝남"
    : start && start > today
      ? `${formatDottedPolicyDeadline(start)} 시작`
      : isDigitalTourismResidentCardPolicy(policy)
        ? "상시 발급"
        : isSafePolicyDeadline(policy.deadline)
          ? `${formatDottedPolicyDeadline(policy.deadline)} 마감`
          : "마감일 확인 필요";
  const how = policyHowTo(policy, kind, text.target);
  return (
    <dl className={how ? "policy-detail-facts" : "policy-detail-facts two"}>
      <div>
        <dt>받는 것</dt>
        {/* 제휴 할인은 제휴처 수가 곧 받는 것이다 */}
        <dd className="amount">{text.partnerCount > 0 ? `제휴처 ${text.partnerCount}곳 할인` : won(amountLabel)}</dd>
      </div>
      <div>
        <dt>기간</dt>
        <dd>{when}</dd>
      </div>
      {how && (
        <div>
          <dt>받는 방법</dt>
          <dd>{how}</dd>
        </div>
      )}
    </dl>
  );
}

export function PolicyBenefitSection({ policy, text }: { policy: Policy; text: PolicyDetailText }) {
  const { place } = policyPlaceAndProgram(policy.title);
  const hasContent =
    Boolean(text.lead || text.spend || text.partnerCount) ||
    [text.more, text.picks, text.conditions, text.steps, text.extra].some((list) => list.length > 0);
  return (
    <Section id="policy-detail-benefit" title="받는 혜택">
      {text.lead && <p className="policy-detail-p">{text.lead}</p>}
      {text.more.map((sentence) => (
        <p className="policy-detail-p" key={sentence}>
          {sentence}
        </p>
      ))}
      {text.spend && (
        <p className="policy-detail-p">
          <b>대상 지출</b> · {text.spend} 등
        </p>
      )}
      {text.partnerCount > 0 && (
        <p className="policy-detail-p">
          <b>제휴처 {text.partnerCount}곳</b>
          {text.partnerMix && ` · ${text.partnerMix}`}
        </p>
      )}
      {text.picks.length > 0 && (
        <>
          <h3>인기 제휴처</h3>
          {/* 제휴처 한 줄 한 줄이 그 제휴처 안내 페이지로 간다(지금 앱과 같은 방식) */}
          <ul className="policy-detail-picks">
            {text.picks.map((pick, index) => (
              <li key={`${pick.url}-${index}`}>
                <a className="policy-detail-pick" href={pick.url} rel="noopener noreferrer" target="_blank">
                  <span className="pick-category">{pick.category || "제휴"}</span>
                  <span className="pick-body">
                    <b>{pick.name}</b>
                    {pick.benefit && <span className="pick-benefit">{pick.benefit}</span>}
                    {pick.note && <span className="pick-note">{pick.note}</span>}
                  </span>
                  <External />
                </a>
              </li>
            ))}
          </ul>
          {text.partnerCount > 0 && policy.officialUrl && (
            <a className="policy-detail-link" href={policy.officialUrl} rel="noopener noreferrer" target="_blank">
              <span>
                {place ?? policy.region} 제휴처 {text.partnerCount}곳 모두 보기
              </span>
              <External />
            </a>
          )}
        </>
      )}
      {text.conditions.length > 0 && (
        <>
          {/* 하나라도 빠지면 환급이 안 되니 원문 그대로 */}
          <h3>혜택 적용 조건</h3>
          <List items={text.conditions} className="strong" />
        </>
      )}
      {text.steps.length > 0 && (
        <>
          <h3>받는 방법</h3>
          <ol className="policy-detail-steps">
            {text.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </>
      )}
      {text.extra.map((group, index) => (
        <Fragment key={`${group.title}-${index}`}>
          {group.title && <h3>{group.title}</h3>}
          <List items={group.items} />
        </Fragment>
      ))}
      {!hasContent && <OfficialMissing what="할인 금액과 조건은" officialUrl={policy.officialUrl} />}
    </Section>
  );
}

function shortDate(iso: string, thisYear: string): string {
  const [year, month, day] = iso.split("-");
  return `${year === thisYear ? "" : `${year}.`}${Number(month)}.${Number(day)}`;
}

export function PolicyPeriodSection({ policy, text }: { policy: Policy; text: PolicyDetailText }) {
  const today = getKstDateInputValue();
  const thisYear = today.slice(0, 4);
  const start = isSafePolicyDeadline(policy.startDate) ? policy.startDate : null;
  const deadline = isSafePolicyDeadline(policy.deadline) ? policy.deadline : null;
  const timeline = policyTimeline(text.periods, start, deadline);
  const rows = timeline.rows.filter((row) => isSafePolicyDeadline(row.start) && isSafePolicyDeadline(row.end));
  const loose = timeline.loose.length > 0 ? <List items={timeline.loose} /> : null;

  let body: ReactNode;
  if (rows.length > 0) {
    const time = (iso: string) => new Date(`${iso}T00:00:00`).getTime();
    const now = time(today);
    const low = Math.min(now, ...rows.map((row) => time(row.start)));
    const high = Math.max(now, ...rows.map((row) => time(row.end)));
    const position = (value: number) => ((value - low) / (high - low || 1)) * 100;
    const todayAt = position(now);
    body = (
      <>
        <div className="policy-timeline">
          {rows.map((row, index) => (
            <div className="policy-timeline-row" key={`${row.label}-${index}`}>
              <span className="policy-timeline-label">{row.label}</span>
              <span className="policy-timeline-track" aria-hidden="true">
                <i
                  style={{
                    left: `${position(time(row.start)).toFixed(1)}%`,
                    width: `${Math.max(2, position(time(row.end)) - position(time(row.start))).toFixed(1)}%`,
                  }}
                />
              </span>
              <span className="policy-timeline-dates">
                {shortDate(row.start, thisYear)} – {shortDate(row.end, thisYear)}
                {row.note === true ? " · 연도는 올해로 봄" : row.note ? ` · ${row.note}` : ""}
              </span>
            </div>
          ))}
          <span
            aria-hidden="true"
            className={`policy-timeline-today${todayAt > 85 ? " right" : todayAt < 15 ? " left" : ""}`}
            style={{ left: `calc(56px + (100% - 56px) * ${(todayAt / 100).toFixed(3)})` }}
          >
            <b>오늘 {shortDate(today, thisYear)}</b>
          </span>
        </div>
        {loose}
      </>
    );
  } else if (isDigitalTourismResidentCardPolicy(policy)) {
    body = (
      <>
        <p className="policy-detail-p">
          <b>제휴처별 운영기간 확인</b>
        </p>
        <p className="policy-detail-p">마감일 없이 주민증을 발급하면 바로 쓸 수 있어요. 할인이 되는 기간은 제휴처마다 달라요.</p>
      </>
    );
  } else if (!deadline) {
    body = (
      <>
        <p className="policy-detail-p">
          <b>마감일 확인 필요</b>
        </p>
        <OfficialMissing what="기간은" officialUrl={policy.officialUrl} />
        {loose}
      </>
    );
  } else {
    body = (
      <>
        <p className="policy-detail-p">
          {formatDottedPolicyDeadline(deadline)}까지{start ? ` · ${formatDottedPolicyDeadline(start)}부터` : ""}
        </p>
        {loose}
      </>
    );
  }
  return (
    <Section id="policy-detail-period" title="기간">
      {body}
    </Section>
  );
}

export function PolicyTargetSection({ policy, text }: { policy: Policy; text: PolicyDetailText }) {
  const islandCount = policy.eligibleIslandCount ?? 0;
  const hasIslands = islandCount > 0 && Boolean(policy.eligibleIslandsOfficialUrl);
  const regionTitle = text.regions[0]?.title;
  return (
    <Section id="policy-detail-target" title="받을 수 있는 사람">
      {text.target.length > 0 && <List items={text.target} />}
      {regionTitle && (
        <>
          <h3>{regionTitle}</h3>
          {/* 도별 곳수는 글로, 전체 목록 안내 문장은 링크로 */}
          {text.regions.map((region, index) =>
            region.url ? (
              <a className="policy-detail-link" href={region.url} key={index} rel="noopener noreferrer" target="_blank">
                <span>시·군·구 전체 목록 보기</span>
                <External />
              </a>
            ) : (
              <p className="policy-detail-p" key={index}>
                {region.description}
              </p>
            ),
          )}
        </>
      )}
      {hasIslands && (
        <div aria-label="대상 섬" className="policy-detail-islands" role="group">
          <h3>대상 섬</h3>
          <p className="policy-detail-p">대상 섬 {islandCount}곳</p>
          <a
            className="policy-detail-link"
            href={policy.eligibleIslandsOfficialUrl ?? undefined}
            rel="noopener noreferrer"
            target="_blank"
          >
            <span>대상 섬 공식 안내</span>
            <External />
          </a>
        </div>
      )}
      {text.target.length === 0 && !regionTitle && !hasIslands && (
        <OfficialMissing what="대상과 조건은" officialUrl={policy.officialUrl} />
      )}
    </Section>
  );
}

export function PolicyDocumentsSection({ policy, text }: { policy: Policy; text: PolicyDetailText }) {
  return (
    <Section id="policy-detail-documents" title="준비물">
      {text.noDocuments !== null && (
        <>
          <p className="policy-detail-ok">
            <Check aria-hidden="true" size={20} strokeWidth={2.2} />
            따로 낼 서류가 없어요
          </p>
          {text.noDocuments && <p className="policy-detail-p">{text.noDocuments}</p>}
        </>
      )}
      {text.documents.length > 0 && <List items={text.documents} />}
      {text.noDocuments === null && text.documents.length === 0 && (
        <OfficialMissing what="필요한 서류는" officialUrl={policy.officialUrl} />
      )}
    </Section>
  );
}

export function PolicyNotesSection({ text }: { text: PolicyDetailText }) {
  return (
    <Section id="policy-detail-notes" title="확인할 점">
      {text.notes.length > 0 && <List items={text.notes} className="muted" />}
      {/* 수집된 일반 안내 여러 줄('공식 안내에서 최종 확인' 류)을 이 한 줄로 */}
      <p className="policy-detail-standard">할인율·기간·조건은 바뀔 수 있어요. 신청 전에 공식 안내에서 최종 확인해 주세요.</p>
    </Section>
  );
}

export function PolicySourceLine({ policy, text }: { policy: Policy; text: PolicyDetailText }) {
  let host = "";
  try {
    host = policy.officialUrl ? new URL(policy.officialUrl).hostname : "";
  } catch {
    host = "";
  }
  if (!host && text.provenance.length === 0) return null;
  return (
    <p className="policy-detail-source">
      출처{" "}
      {host && policy.officialUrl ? (
        <a href={policy.officialUrl} rel="noopener noreferrer" target="_blank">
          {host}
        </a>
      ) : (
        "공식 안내"
      )}
      {text.provenance.map((line) => ` · ${line}`)}
    </p>
  );
}
