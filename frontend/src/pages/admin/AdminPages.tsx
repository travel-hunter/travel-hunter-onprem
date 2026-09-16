import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { ApiError, appDataApi, type AdminAuditLogListItem, type AdminCollectionSource, type AdminCollectionSourceUpdate, type AdminEligibleIslandSnapshot, type AdminEligibleIslandSnapshotDetail, type AdminExternalSourceSummaryResponse, type AdminPolicyDetail, type AdminPolicyListItem, type AdminPolicyReviewCandidate, type AdminPolicyStatus, type AdminUserDetail, type AdminUserListItem, type ExternalCollectionOpsHealth, type ExternalCollectionRunResponse } from "../../api";

function adminNavClass({ isActive }: { isActive: boolean }) {
  return isActive ? "admin-nav-link active" : "admin-nav-link";
}

function toLines(value: string): string[] {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function fieldId(name: string) {
  return `admin-field-${name}`;
}

const ADMIN_PAGE_SIZE = 30;

const ADMIN_POLICY_STATUS_TABS: Array<{ label: string; value: "all" | AdminPolicyStatus }> = [
  { label: "전체", value: "all" },
  { label: "노출중", value: "active" },
  { label: "숨김", value: "hidden" },
];

function formatAdminDateTime(value: string | null) {
  if (!value) return "기록 없음";
  return value.replace("T", " ").slice(0, 16);
}

export function AdminLayout() {
  return (
    <div className="admin-layout">
      <aside className="admin-sidebar" aria-label="관리자 메뉴">
        <Link className="admin-logo" to="/admin">
          <span aria-hidden="true">TH</span>
          <strong>관리자</strong>
        </Link>
        <nav>
          <NavLink className={adminNavClass} to="/admin/users">회원 관리</NavLink>
          <NavLink className={adminNavClass} to="/admin/policies">정책 관리</NavLink>
          <NavLink className={adminNavClass} to="/admin/policy-review">수집 검토</NavLink>
          <NavLink className={adminNavClass} to="/admin/audit-logs">변경 이력</NavLink>
          <NavLink className="admin-nav-link" to="/home">서비스로 이동</NavLink>
        </nav>
      </aside>
      <main className="admin-main">
        <Outlet />
      </main>
    </div>
  );
}

export function AdminForbiddenPage() {
  return (
    <main className="admin-forbidden-page">
      <section className="admin-forbidden-card">
        <span aria-hidden="true">403</span>
        <h1>접근 권한이 없습니다</h1>
        <p>이 페이지는 관리자만 접근할 수 있습니다.</p>
        <Link to="/home">홈으로 돌아가기</Link>
      </section>
    </main>
  );
}

export function AdminDashboardPage() {
  const [summary, setSummary] = useState<AdminExternalSourceSummaryResponse | null>(null);
  const [opsHealth, setOpsHealth] = useState<ExternalCollectionOpsHealth | null>(null);
  const [runResult, setRunResult] = useState<ExternalCollectionRunResponse | null>(null);
  const [summaryError, setSummaryError] = useState("");
  const [isRunningCollection, setIsRunningCollection] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSummaryError("");
    Promise.all([
      appDataApi.getAdminExternalSourceSummary(),
      appDataApi.getExternalCollectionOpsHealth(),
    ])
      .then(([summaryResponse, healthResponse]) => {
        if (cancelled) return;
        setSummary(summaryResponse);
        setOpsHealth(healthResponse);
      })
      .catch(() => {
        if (!cancelled) setSummaryError("외부 정책 수집 상태를 불러오지 못했습니다.");
      });
    return () => { cancelled = true; };
  }, []);

  const runCollection = async () => {
    setIsRunningCollection(true);
    setSummaryError("");
    setRunResult(null);
    try {
      const result = await appDataApi.runExternalCollection();
      const [summaryResponse, healthResponse] = await Promise.all([
        appDataApi.getAdminExternalSourceSummary(),
        appDataApi.getExternalCollectionOpsHealth(),
      ]);
      setRunResult(result);
      setSummary(summaryResponse);
      setOpsHealth(healthResponse);
    } catch {
      setSummaryError("외부 정책 수집 실행에 실패했습니다. 공식 사이트 연결과 서버 로그를 확인하세요.");
    } finally {
      setIsRunningCollection(false);
    }
  };

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>Travel Hunter Admin</p>
          <h1>관리자 페이지</h1>
        </div>
      </div>
      <div className="admin-dashboard-grid">
        <Link className="admin-dashboard-card" to="/admin/users">
          <span>회원</span>
          <strong>회원 정보 확인 및 수정</strong>
          <p>닉네임, 프로필 선택값, 관리자 역할을 안전한 범위 안에서 관리합니다.</p>
        </Link>
        <Link className="admin-dashboard-card" to="/admin/policies">
          <span>정책</span>
          <strong>정책 추가 및 수정</strong>
          <p>정책 노출 상태, 신청 조건, 필요 서류, 공식 링크를 관리합니다.</p>
        </Link>
        <Link className="admin-dashboard-card" to="/admin/audit-logs">
          <span>이력</span>
          <strong>관리자 변경 이력</strong>
          <p>회원과 정책 변경 내역을 감사 로그로 확인합니다.</p>
        </Link>
      </div>
      <section className="admin-external-source-panel" aria-label="외부 정책 수집 상태">
        <div className="admin-section-head">
          <div>
            <p>External sources</p>
            <h2>외부 정책 수집 상태</h2>
          </div>
          <div className="admin-section-actions">
            <span>최근 확인 {formatAdminDateTime(summary?.latestFetchedAt ?? null)}</span>
            <button className="btn secondary" type="button" onClick={runCollection} disabled={isRunningCollection}>
              {isRunningCollection ? "수집 중" : "지금 수집 실행"}
            </button>
          </div>
        </div>
        {summaryError && <p className="form-error">{summaryError}</p>}
        {opsHealth && (
          <p className="admin-muted">
            자동 수집 {opsHealth.schedulerEnabled ? "켜짐" : "꺼짐"} · 실행 시각 {opsHealth.runAt} · 마지막 결과 {opsHealth.lastOutcome ?? "기록 없음"}
          </p>
        )}
        {runResult && (
          <p className="admin-notice">
            수집 결과 {runResult.outcome} · 파싱 {runResult.parsedCount}건 · 반영 {runResult.createdOrUpdatedCount}건
          </p>
        )}
        {summary && (
          <>
            <div className="admin-source-overview">
              <span><strong>{summary.totalRecords}</strong> 전체 원천</span>
              <span><strong>{summary.activeRecords}</strong> 접수중</span>
              <span><strong>{summary.freshRecords}</strong> 최신 확인</span>
              <span><strong>{summary.promotedPolicyCount}</strong> 서비스 노출</span>
            </div>
            <div className="admin-source-list">
              {summary.items.map((item) => (
                <article className="admin-source-card" key={item.sourceCategory}>
                  <div>
                    <span className="admin-source-label">{item.label}</span>
                    <strong>{item.sourceName}</strong>
                  </div>
                  <dl>
                    <div><dt>원천</dt><dd>{item.totalRecords}</dd></div>
                    <div><dt>접수중</dt><dd>{item.activeRecords}</dd></div>
                    <div><dt>마감</dt><dd>{item.endedRecords}</dd></div>
                    <div><dt>노출</dt><dd>{item.activePromotedPolicyCount}</dd></div>
                  </dl>
                  <p>마지막 확인 {formatAdminDateTime(item.latestVerifiedAt ?? item.latestFetchedAt)}</p>
                </article>
              ))}
              {summary.items.length === 0 && <p className="admin-empty">외부 수집 기록이 없습니다.</p>}
            </div>
          </>
        )}
      </section>
    </section>
  );
}

export function AdminUsersPage() {
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(ADMIN_PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    appDataApi.listAdminUsers({ limit: ADMIN_PAGE_SIZE, offset })
      .then((response) => {
        if (cancelled) return;
        setUsers(response.items);
        setTotal(response.total);
        setLimit(response.limit);
      })
      .catch(() => { if (!cancelled) setError("회원 목록을 불러오지 못했습니다."); });
    return () => { cancelled = true; };
  }, [offset]);

  const visibleStart = total === 0 ? 0 : offset + 1;
  const visibleEnd = Math.min(offset + users.length, total);
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const canMovePrev = offset > 0;
  const canMoveNext = offset + limit < total;

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>Users</p>
          <h1>회원 관리</h1>
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="admin-list-toolbar">
        <p className="admin-result-count">총 {total}명 중 {visibleStart}-{visibleEnd}명 표시</p>
      </div>
      <div className="admin-table-card">
        {users.map((user) => (
          <Link className="admin-row" key={user.id} to={`/admin/users/${user.id}`}>
            <strong>{user.email}</strong>
            <span>{user.nickname}</span>
            <em>{user.role}</em>
          </Link>
        ))}
        {users.length === 0 && !error && <p className="admin-empty">표시할 회원이 없습니다.</p>}
      </div>
      <div className="admin-pagination" aria-label="회원 목록 페이지 이동">
        <button disabled={!canMovePrev} onClick={() => setOffset((current) => Math.max(0, current - limit))} type="button">
          이전
        </button>
        <span>{currentPage} / {totalPages}</span>
        <button disabled={!canMoveNext} onClick={() => setOffset((current) => current + limit)} type="button">
          다음
        </button>
      </div>
    </section>
  );
}

export function AdminUserDetailPage() {
  const { userId = "" } = useParams();
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    appDataApi.getAdminUser(userId)
      .then((nextUser) => { if (!cancelled) setUser(nextUser); })
      .catch(() => { if (!cancelled) setError("회원 정보를 불러오지 못했습니다."); });
    return () => { cancelled = true; };
  }, [userId]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    if (!user) return;
    setError("");
    setNotice("");
    try {
      const saved = await appDataApi.updateAdminUser(user.id, {
        nickname: user.nickname,
        preferredRegions: user.preferredRegions,
        travelStyle: user.travelStyle,
        travelBudget: user.travelBudget,
        onboardingCompleted: user.onboardingCompleted,
        role: user.role,
      });
      setUser(saved);
      setNotice("저장했습니다.");
    } catch {
      setError("회원 정보를 저장하지 못했습니다.");
    }
  };

  if (!user) {
    return <section className="admin-page"><h1>회원 관리</h1>{error || "불러오는 중"}</section>;
  }

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>{user.email}</p>
          <h1>회원 상세</h1>
        </div>
      </div>
      <form className="admin-form-card" onSubmit={save}>
        <label htmlFor={fieldId("nickname")}>닉네임</label>
        <input id={fieldId("nickname")} value={user.nickname} onChange={(event) => setUser({ ...user, nickname: event.target.value })} />
        <label htmlFor={fieldId("role")}>역할</label>
        <select id={fieldId("role")} value={user.role} onChange={(event) => setUser({ ...user, role: event.target.value as "user" | "admin" })}>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <label htmlFor={fieldId("preferred")}>선호 지역</label>
        <input id={fieldId("preferred")} value={user.preferredRegions ?? ""} onChange={(event) => setUser({ ...user, preferredRegions: event.target.value })} />
        <label htmlFor={fieldId("style")}>여행 스타일</label>
        <input id={fieldId("style")} value={user.travelStyle ?? ""} onChange={(event) => setUser({ ...user, travelStyle: event.target.value })} />
        <label htmlFor={fieldId("budget")}>예산</label>
        <input id={fieldId("budget")} value={user.travelBudget ?? ""} onChange={(event) => setUser({ ...user, travelBudget: event.target.value })} />
        <label className="admin-check"><input type="checkbox" checked={user.onboardingCompleted} onChange={(event) => setUser({ ...user, onboardingCompleted: event.target.checked })} /> 온보딩 완료</label>
        {error && <p className="form-error">{error}</p>}
        {notice && <p className="admin-notice">{notice}</p>}
        <button className="btn primary" type="submit">저장</button>
      </form>
    </section>
  );
}

export function AdminPoliciesPage() {
  const [policies, setPolicies] = useState<AdminPolicyListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<"all" | AdminPolicyStatus>("all");
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(ADMIN_PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    appDataApi.listAdminPolicies({
      limit: ADMIN_PAGE_SIZE,
      offset,
      ...(statusFilter === "all" ? {} : { status: statusFilter }),
    })
      .then((response) => {
        if (cancelled) return;
        setPolicies(response.items);
        setTotal(response.total);
        setLimit(response.limit);
      })
      .catch(() => { if (!cancelled) setError("정책 목록을 불러오지 못했습니다."); });
    return () => { cancelled = true; };
  }, [offset, statusFilter]);

  const visibleStart = total === 0 ? 0 : offset + 1;
  const visibleEnd = Math.min(offset + policies.length, total);
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const canMovePrev = offset > 0;
  const canMoveNext = offset + limit < total;

  const selectStatusFilter = (value: "all" | AdminPolicyStatus) => {
    setStatusFilter(value);
    setOffset(0);
  };

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>Policies</p>
          <h1>정책 관리</h1>
        </div>
        <Link className="btn primary" to="/admin/policies/new">정책 추가</Link>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="admin-list-toolbar">
        <div className="admin-status-tabs" aria-label="정책 노출 상태">
          {ADMIN_POLICY_STATUS_TABS.map((tab) => (
            <button
              aria-pressed={statusFilter === tab.value}
              className={statusFilter === tab.value ? "admin-status-tab active" : "admin-status-tab"}
              key={tab.value}
              onClick={() => selectStatusFilter(tab.value)}
              type="button"
            >
              {tab.label}
            </button>
          ))}
        </div>
        <p className="admin-result-count">총 {total}개 중 {visibleStart}-{visibleEnd}개 표시</p>
      </div>
      <div className="admin-table-card">
        {policies.map((policy) => (
          <Link className="admin-row" key={policy.id} to={`/admin/policies/${policy.id}`}>
            <strong>{policy.title}</strong>
            <span>{policy.region} · <i className="admin-source-label">{policy.sourceLabel}</i></span>
            <em>{policy.status}</em>
          </Link>
        ))}
        {policies.length === 0 && !error && <p className="admin-empty">표시할 정책이 없습니다.</p>}
      </div>
      <div className="admin-pagination" aria-label="정책 목록 페이지 이동">
        <button disabled={!canMovePrev} onClick={() => setOffset((current) => Math.max(0, current - limit))} type="button">
          이전
        </button>
        <span>{currentPage} / {totalPages}</span>
        <button disabled={!canMoveNext} onClick={() => setOffset((current) => current + limit)} type="button">
          다음
        </button>
      </div>
    </section>
  );
}

const emptyPolicy: AdminPolicyDetail = {
  id: "",
  slug: "",
  title: "",
  organization: "",
  policyType: "지역할인",
  region: "전국",
  status: "active",
  sourceType: "internal",
  sourceCategory: null,
  sourceLabel: "내부",
  updatedAt: "",
  startDate: null,
  endDate: null,
  benefitAmount: null,
  benefitDetail: "",
  description: "",
  requirements: [],
  documents: [],
  officialUrl: "",
  applyUrl: null,
  policyComment: "",
  policyPeriod: null,
  adminOverrideEnabled: false,
  createdAt: "",
};

export function AdminPolicyEditorPage({ mode = "edit" }: { mode?: "create" | "edit" }) {
  const { policyId = "" } = useParams();
  const navigate = useNavigate();
  const isCreate = mode === "create";
  const [policy, setPolicy] = useState<AdminPolicyDetail>(emptyPolicy);
  const [requirementsText, setRequirementsText] = useState("");
  const [documentsText, setDocumentsText] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (isCreate) {
      setPolicy(emptyPolicy);
      setRequirementsText("");
      setDocumentsText("");
      return;
    }
    let cancelled = false;
    appDataApi.getAdminPolicy(policyId)
      .then((nextPolicy) => {
        if (cancelled) return;
        setPolicy(nextPolicy);
        setRequirementsText(nextPolicy.requirements.join("\n"));
        setDocumentsText(nextPolicy.documents.join("\n"));
      })
      .catch(() => { if (!cancelled) setError("정책 정보를 불러오지 못했습니다."); });
    return () => { cancelled = true; };
  }, [isCreate, policyId]);

  const payload = useMemo(() => ({
    title: policy.title,
    organization: policy.organization || null,
    policyType: policy.policyType || "지역할인",
    region: policy.region,
    startDate: policy.startDate || null,
    endDate: policy.endDate || null,
    benefitAmount: policy.benefitAmount,
    benefitDetail: policy.benefitDetail || null,
    description: policy.description || null,
    requirements: toLines(requirementsText),
    documents: toLines(documentsText),
    officialUrl: policy.officialUrl || null,
    applyUrl: policy.applyUrl || null,
    policyComment: policy.policyComment || null,
    policyPeriod: policy.policyPeriod || null,
    status: policy.status,
  }), [documentsText, policy, requirementsText]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setNotice("");
    try {
      if (isCreate) {
        const saved = await appDataApi.createAdminPolicy({ ...payload, slug: policy.slug });
        navigate(`/admin/policies/${saved.id}`, { replace: true });
      } else {
        const saved = await appDataApi.updateAdminPolicy(policy.id, payload);
        setPolicy(saved);
        setNotice("저장했습니다.");
      }
    } catch {
      setError("정책을 저장하지 못했습니다.");
    }
  };

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>{isCreate ? "New policy" : policy.slug}</p>
          <h1>{isCreate ? "정책 추가" : "정책 상세"}</h1>
        </div>
      </div>
      <form className="admin-form-card" onSubmit={save}>
        <label htmlFor={fieldId("policy-slug")}>정책 slug</label>
        <input id={fieldId("policy-slug")} disabled={!isCreate} value={policy.slug} onChange={(event) => setPolicy({ ...policy, slug: event.target.value })} />
        <label htmlFor={fieldId("policy-title")}>정책 제목</label>
        <input id={fieldId("policy-title")} aria-label="정책 제목" value={policy.title} onChange={(event) => setPolicy({ ...policy, title: event.target.value })} />
        <label htmlFor={fieldId("policy-org")}>기관</label>
        <input id={fieldId("policy-org")} value={policy.organization ?? ""} onChange={(event) => setPolicy({ ...policy, organization: event.target.value })} />
        <label htmlFor={fieldId("policy-type")}>분류</label>
        <input id={fieldId("policy-type")} value={policy.policyType ?? ""} onChange={(event) => setPolicy({ ...policy, policyType: event.target.value })} />
        <label htmlFor={fieldId("policy-region")}>지역</label>
        <input id={fieldId("policy-region")} value={policy.region} onChange={(event) => setPolicy({ ...policy, region: event.target.value })} />
        <label htmlFor={fieldId("policy-end")}>종료일</label>
        <input id={fieldId("policy-end")} type="date" value={policy.endDate ?? ""} onChange={(event) => setPolicy({ ...policy, endDate: event.target.value || null })} />
        <label htmlFor={fieldId("policy-amount")}>혜택 금액</label>
        <input id={fieldId("policy-amount")} type="number" value={policy.benefitAmount ?? ""} onChange={(event) => setPolicy({ ...policy, benefitAmount: event.target.value ? Number(event.target.value) : null })} />
        <label htmlFor={fieldId("policy-benefit")}>혜택 설명</label>
        <input id={fieldId("policy-benefit")} value={policy.benefitDetail ?? ""} onChange={(event) => setPolicy({ ...policy, benefitDetail: event.target.value })} />
        <label htmlFor={fieldId("policy-description")}>상세 설명</label>
        <textarea id={fieldId("policy-description")} value={policy.description ?? ""} onChange={(event) => setPolicy({ ...policy, description: event.target.value })} />
        <label htmlFor={fieldId("policy-requirements")}>신청 조건</label>
        <textarea id={fieldId("policy-requirements")} value={requirementsText} onChange={(event) => setRequirementsText(event.target.value)} />
        <label htmlFor={fieldId("policy-documents")}>필요 서류</label>
        <textarea id={fieldId("policy-documents")} value={documentsText} onChange={(event) => setDocumentsText(event.target.value)} />
        <label htmlFor={fieldId("policy-official")}>공식 URL</label>
        <input id={fieldId("policy-official")} value={policy.officialUrl ?? ""} onChange={(event) => setPolicy({ ...policy, officialUrl: event.target.value })} />
        <label htmlFor={fieldId("policy-apply")}>신청 URL</label>
        <input id={fieldId("policy-apply")} value={policy.applyUrl ?? ""} onChange={(event) => setPolicy({ ...policy, applyUrl: event.target.value })} />
        <label htmlFor={fieldId("policy-status")}>노출 상태</label>
        <select id={fieldId("policy-status")} value={policy.status} onChange={(event) => setPolicy({ ...policy, status: event.target.value as "active" | "hidden" })}>
          <option value="active">active</option>
          <option value="hidden">hidden</option>
        </select>
        <p className="admin-readonly">slug와 sourceType은 수정 요청에 포함하지 않습니다. 현재 sourceType: {policy.sourceType}</p>
        {error && <p className="form-error">{error}</p>}
        {notice && <p className="admin-notice">{notice}</p>}
        <button className="btn primary" type="submit">저장</button>
      </form>
    </section>
  );
}

export function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<AdminAuditLogListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [limit, setLimit] = useState(ADMIN_PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    setError("");
    appDataApi.listAdminAuditLogs({ limit: ADMIN_PAGE_SIZE, offset })
      .then((response) => {
        if (cancelled) return;
        setLogs(response.items);
        setTotal(response.total);
        setLimit(response.limit);
      })
      .catch(() => { if (!cancelled) setError("변경 이력을 불러오지 못했습니다."); });
    return () => { cancelled = true; };
  }, [offset]);

  const visibleStart = total === 0 ? 0 : offset + 1;
  const visibleEnd = Math.min(offset + logs.length, total);
  const currentPage = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const canMovePrev = offset > 0;
  const canMoveNext = offset + limit < total;

  return (
    <section className="admin-page">
      <div className="admin-page-head">
        <div>
          <p>Audit</p>
          <h1>변경 이력</h1>
        </div>
      </div>
      {error && <p className="form-error">{error}</p>}
      <div className="admin-list-toolbar">
        <p className="admin-result-count">총 {total}개 중 {visibleStart}-{visibleEnd}개 표시</p>
      </div>
      <div className="admin-table-card">
        {logs.map((log) => (
          <article className="admin-row" key={log.id}>
            <strong>{log.action}</strong>
            <span>{log.adminEmail}</span>
            <em>{log.createdAt}</em>
          </article>
        ))}
        {logs.length === 0 && !error && <p className="admin-empty">기록된 변경 이력이 없습니다.</p>}
      </div>
      <div className="admin-pagination" aria-label="변경 이력 페이지 이동">
        <button disabled={!canMovePrev} onClick={() => setOffset((current) => Math.max(0, current - limit))} type="button">
          이전
        </button>
        <span>{currentPage} / {totalPages}</span>
        <button disabled={!canMoveNext} onClick={() => setOffset((current) => current + limit)} type="button">
          다음
        </button>
      </div>
    </section>
  );
}


const REVIEW_PAGE_SIZE = 50;

/** Why the auto-publish gate left a candidate for a human (backend review_reason). */
const REVIEW_REASON_LABEL: Record<string, string> = {
  source_mode_review: "전건 검토 소스",
  first_baseline: "첫 기준선",
  new_policy: "새 정책",
  identity_changed: "제목·지역 변경",
  source_anomaly: "소스 이상",
  would_publish_hidden: "비공개 예정",
  low_confidence: "신뢰도 낮음",
  stay_discount_manual: "숙박세일 수동",
  procedure_changed: "신청 절차 변경",
};

export function AdminPolicyReviewPage() {
  const [candidates, setCandidates] = useState<AdminPolicyReviewCandidate[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [sources, setSources] = useState<AdminCollectionSource[]>([]);
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState<string | null>(null);

  const load = async () => {
    setError("");
    try {
      const [candidateResponse, sourceResponse] = await Promise.all([
        appDataApi.listAdminPolicyReviewCandidates({ limit: REVIEW_PAGE_SIZE, offset }),
        appDataApi.listAdminCollectionSources(),
      ]);
      setCandidates(candidateResponse.items);
      setTotal(candidateResponse.total);
      setSelectedIds([]);
      setSources(sourceResponse.items);
    } catch {
      setError("수집 검토 정보를 불러오지 못했습니다.");
    }
  };

  useEffect(() => { void load(); }, [offset]);

  const totalPages = Math.max(1, Math.ceil(total / REVIEW_PAGE_SIZE));
  const currentPage = Math.floor(offset / REVIEW_PAGE_SIZE) + 1;

  const toggleSelected = (candidateId: string) => {
    setSelectedIds((current) => current.includes(candidateId) ? current.filter((id) => id !== candidateId) : [...current, candidateId]);
  };

  const approveBatch = async (mode: "selected" | "all") => {
    const message = mode === "all"
      ? `검토 대기 정책 전체 ${total}건을 승인하고 공개합니다. 되돌릴 수 없습니다. 계속할까요?`
      : `선택한 ${selectedIds.length}건을 승인하고 공개합니다. 계속할까요?`;
    if (!window.confirm(message)) return;
    setWorkingId("batch");
    setError("");
    try {
      await appDataApi.approveAdminPolicyReviewCandidates(
        mode === "all" ? { candidateIds: [], approveAll: true } : { candidateIds: selectedIds, approveAll: false },
      );
      await load();
    } catch (cause) {
      const reason = cause instanceof ApiError && cause.status === 409 ? ` 사유: ${cause.message}` : "";
      setError(`일괄 승인에 실패했습니다. 이 요청의 후보는 하나도 공개되지 않았습니다.${reason} 문제 후보를 반려하거나 선택에서 빼고 다시 시도하세요.`);
    } finally {
      setWorkingId(null);
    }
  };

  const decide = async (candidate: AdminPolicyReviewCandidate, decision: "approve" | "reject") => {
    const note = decision === "reject" ? window.prompt("반려 사유를 입력하세요.") : undefined;
    if (decision === "reject" && !note?.trim()) return;
    setWorkingId(candidate.id);
    setError("");
    try {
      if (decision === "approve") {
        await appDataApi.approveAdminPolicyReviewCandidate(candidate.id);
      } else {
        await appDataApi.rejectAdminPolicyReviewCandidate(candidate.id, note?.trim() ?? "");
      }
      await load();
    } catch {
      setError("검토 처리에 실패했습니다. 새로고침 후 다시 시도하세요.");
    } finally {
      setWorkingId(null);
    }
  };

  const patchSource = async (source: AdminCollectionSource, patch: AdminCollectionSourceUpdate, failure: string) => {
    setWorkingId(source.key);
    setError("");
    try {
      const updated = await appDataApi.updateAdminCollectionSource(source.key, patch);
      setSources((current) => current.map((item) => item.key === updated.key ? updated : item));
    } catch (cause) {
      const reason = cause instanceof ApiError && cause.status === 409 && cause.message === "baseline_required"
        ? " 이 소스에서 관리자가 직접 승인한 후보가 먼저 1건 이상 있어야 합니다."
        : "";
      setError(`${failure}${reason}`);
    } finally {
      setWorkingId(null);
    }
  };

  const toggleSource = (source: AdminCollectionSource) =>
    patchSource(source, { enabled: !source.enabled }, "수집 소스 설정을 바꾸지 못했습니다.");

  const toggleAutoPublish = (source: AdminCollectionSource) => {
    const turningOn = source.publicationMode !== "auto_after_reviewed_baseline";
    if (
      turningOn &&
      !window.confirm(`${source.displayName}의 정상 갱신을 관리자 확인 없이 자동 발행합니다.\n새 정책·제목/지역 변경·소스 이상은 계속 검토 대기로 남습니다. 켤까요?`)
    ) {
      return;
    }
    return patchSource(
      source,
      { publicationMode: turningOn ? "auto_after_reviewed_baseline" : "review" },
      "자동 발행 설정을 바꾸지 못했습니다.",
    );
  };

  return (
    <section className="admin-page">
      <div className="admin-page-head"><div><p>Collection review</p><h1>수집 검토</h1></div><button className="btn secondary" type="button" onClick={load}>새로고침</button></div>
      <p className="admin-muted">수집된 정보는 승인 전까지 서비스 정책 카드에 노출되지 않습니다.</p>
      {error && <p className="form-error">{error}</p>}
      <section className="admin-table-card" style={{ padding: 20, marginBottom: 20 }}>
        <div className="admin-section-head"><div><p>Official sources</p><h2>수집 소스</h2></div></div>
        <div className="admin-source-list">{sources.map((source) => (
          <article className="admin-source-card" key={source.key}>
            <div><span className="admin-source-label">{source.enabled ? "사용 중" : "비활성"}</span><strong>{source.displayName}</strong></div>
            <p>{source.sourceCategory} · {formatAdminDateTime(source.lastCollectedAt)}</p>
            <p>
              {source.publicationMode === "auto_after_reviewed_baseline" ? "자동 발행 중" : "전건 검토"}
              {" · "}최근 24시간 자동 발행 {source.autoApprovedLast24h ?? 0}건
              {" · "}기준 건수 {source.expectedMinRecords ?? 0}{source.lastParsedCount != null ? ` (최근 ${source.lastParsedCount}건)` : ""}
            </p>
            <div className="admin-section-actions">
              <button className="btn secondary" type="button" disabled={workingId === source.key} onClick={() => toggleSource(source)}>{source.enabled ? "수집 중지" : "수집 활성화"}</button>
              {source.sourceCategory !== "stay_discount" && (
                <button className="btn secondary" type="button" disabled={workingId === source.key} onClick={() => toggleAutoPublish(source)}>
                  {source.publicationMode === "auto_after_reviewed_baseline" ? "검토로 되돌리기" : "자동 발행 켜기"}
                </button>
              )}
            </div>
          </article>
        ))}</div>
      </section>
      <section className="admin-table-card" style={{ padding: 20 }}>
        <div className="admin-section-head">
          <div><p>Pending · {total}건</p><h2>검토 대기 정책</h2></div>
          <div className="admin-section-actions">
            <button className="btn secondary" type="button" disabled={workingId === "batch" || selectedIds.length === 0} onClick={() => approveBatch("selected")}>선택 승인</button>
            <button className="btn primary" type="button" disabled={workingId === "batch" || total === 0} onClick={() => approveBatch("all")}>전체 승인</button>
          </div>
        </div>
        <div className="admin-source-list">{candidates.map((candidate) => (
          <article className="admin-source-card" key={candidate.id}>
            <div>
              <input aria-label={`${candidate.title} 선택`} checked={selectedIds.includes(candidate.id)} onChange={() => toggleSelected(candidate.id)} type="checkbox" />
              <span className="admin-source-label">{candidate.changeKind === "new" ? "신규" : "변경"}</span>
              {candidate.reviewReason && REVIEW_REASON_LABEL[candidate.reviewReason] && (
                <span className="admin-source-label">{REVIEW_REASON_LABEL[candidate.reviewReason]}</span>
              )}
              <strong>{candidate.title}</strong>
            </div>
            <p>{candidate.region ?? "전국"} · {candidate.benefitText}</p>
            <p><a href={candidate.officialUrl} target="_blank" rel="noreferrer">공식 원문 보기</a></p>
            <div className="admin-section-actions"><button className="btn secondary" type="button" disabled={workingId === candidate.id} onClick={() => decide(candidate, "reject")}>반려</button><button className="btn primary" type="button" disabled={workingId === candidate.id} onClick={() => decide(candidate, "approve")}>승인하고 공개</button></div>
          </article>
        ))}{candidates.length === 0 && <p className="admin-empty">검토 대기 정책이 없습니다.</p>}</div>
        <div className="admin-pagination" aria-label="검토 대기 정책 페이지 이동">
          <button disabled={offset === 0} onClick={() => setOffset((current) => Math.max(0, current - REVIEW_PAGE_SIZE))} type="button">이전</button>
          <span>{currentPage} / {totalPages}</span>
          <button disabled={offset + REVIEW_PAGE_SIZE >= total} onClick={() => setOffset((current) => current + REVIEW_PAGE_SIZE)} type="button">다음</button>
        </div>
      </section>
      <AdminEligibleIslandCatalogSection />
    </section>
  );
}

const ISLAND_SNAPSHOT_STATUS_LABEL: Record<AdminEligibleIslandSnapshot["reviewStatus"], string> = {
  pending: "검토 대기",
  approved: "승인됨",
  rejected: "반려됨",
  superseded: "대체됨",
};

const ISLAND_COLLECT_OUTCOME_LABEL: Record<string, string> = {
  created: "새 갱신 후보를 만들었습니다.",
  unchanged: "첨부 파일이 마지막 확인과 같습니다. 변경 없음.",
  identical: "첨부는 바뀌었지만 대상 섬 목록은 승인본과 같습니다.",
  suspicious_shrink: "승인본보다 30% 넘게 줄어 후보를 만들지 않았습니다. 출처를 직접 확인하세요.",
  download_failed: "공지 또는 첨부 파일을 내려받지 못했습니다.",
  parser_changed: "첨부 파일 형식이 달라져 읽지 못했습니다. 파서 점검이 필요합니다.",
};

/** Catalog snapshot review — deliberately separate from policy review candidates; snapshot-level approval only. */
function AdminEligibleIslandCatalogSection() {
  const [snapshots, setSnapshots] = useState<AdminEligibleIslandSnapshot[]>([]);
  const [approvedEntryCount, setApprovedEntryCount] = useState(0);
  const [detail, setDetail] = useState<AdminEligibleIslandSnapshotDetail | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState<string | null>(null);

  const load = async () => {
    setError("");
    try {
      const response = await appDataApi.listAdminEligibleIslandSnapshots();
      setSnapshots(response.items);
      setApprovedEntryCount(response.approvedEntryCount);
    } catch {
      setError("대상 섬 목록 갱신 정보를 불러오지 못했습니다.");
    }
  };

  useEffect(() => { void load(); }, []);

  const collect = async () => {
    setWorkingId("collect");
    setError("");
    setNotice("");
    try {
      const result = await appDataApi.collectAdminEligibleIslandCatalog();
      setNotice(`${ISLAND_COLLECT_OUTCOME_LABEL[result.outcome] ?? result.outcome}${result.error ? ` (${result.error})` : ""}`);
      await load();
    } catch {
      setError("공지 확인을 실행하지 못했습니다.");
    } finally {
      setWorkingId(null);
    }
  };

  const approve = async (snapshot: AdminEligibleIslandSnapshot) => {
    const confirmed = window.confirm(
      `대상 섬 카탈로그를 이 스냅샷으로 교체합니다.\n총 ${snapshot.entryCount}곳 · 추가 ${snapshot.addedCount} · 삭제 ${snapshot.removedCount} · 변경 ${snapshot.changedCount}\n승인하면 일정 추천에 바로 반영됩니다. 계속할까요?`,
    );
    if (!confirmed) return;
    setWorkingId(snapshot.id);
    setError("");
    try {
      await appDataApi.approveAdminEligibleIslandSnapshot(snapshot.id);
      setDetail(null);
      await load();
    } catch {
      setError("카탈로그 승인에 실패했습니다. 이미 처리된 후보일 수 있으니 새로고침하세요.");
    } finally {
      setWorkingId(null);
    }
  };

  const reject = async (snapshot: AdminEligibleIslandSnapshot) => {
    const note = window.prompt("반려 사유를 입력하세요.");
    if (!note?.trim()) return;
    setWorkingId(snapshot.id);
    setError("");
    try {
      await appDataApi.rejectAdminEligibleIslandSnapshot(snapshot.id, note.trim());
      setDetail(null);
      await load();
    } catch {
      setError("카탈로그 반려에 실패했습니다. 새로고침 후 다시 시도하세요.");
    } finally {
      setWorkingId(null);
    }
  };

  const toggleDetail = async (snapshot: AdminEligibleIslandSnapshot) => {
    if (detail?.snapshot.id === snapshot.id) {
      setDetail(null);
      return;
    }
    setError("");
    try {
      setDetail(await appDataApi.getAdminEligibleIslandSnapshot(snapshot.id));
    } catch {
      setError("스냅샷 상세를 불러오지 못했습니다.");
    }
  };

  return (
    <section className="admin-table-card" style={{ padding: 20, marginTop: 20 }}>
      <div className="admin-section-head">
        <div><p>Eligible island catalog</p><h2>대상 섬 목록 갱신</h2></div>
        <button className="btn secondary" type="button" disabled={workingId === "collect"} onClick={collect}>공지 다시 확인</button>
      </div>
      <p className="admin-muted">현재 승인된 대상 섬 {approvedEntryCount}곳. 승인 전 후보는 정책 카드와 일정 추천에 영향을 주지 않으며, 섬 단위가 아니라 스냅샷 단위로만 승인합니다.</p>
      {notice && <p className="admin-muted">{notice}</p>}
      {error && <p className="form-error">{error}</p>}
      <div className="admin-source-list">{snapshots.map((snapshot) => (
        <article className="admin-source-card" key={snapshot.id}>
          <div>
            <span className="admin-source-label">{snapshot.isCurrentApproved ? "현재 승인본" : ISLAND_SNAPSHOT_STATUS_LABEL[snapshot.reviewStatus]}</span>
            <strong>{snapshot.sourceNoticeTitle ?? "대상 섬 공지"}</strong>
          </div>
          <p>총 {snapshot.entryCount}곳 · <span>추가 {snapshot.addedCount} · 삭제 {snapshot.removedCount} · 변경 {snapshot.changedCount}</span></p>
          <p>수집 {formatAdminDateTime(snapshot.fetchedAt)} · 파서 {snapshot.parserVersion}{snapshot.reviewNote ? ` · 반려 사유: ${snapshot.reviewNote}` : ""}</p>
          <p>
            {snapshot.sourceNoticeUrl && <a href={snapshot.sourceNoticeUrl} target="_blank" rel="noreferrer">공식 공지</a>}
            {snapshot.attachmentFiles.map((file) => (
              <span key={file.sha256}> · <a href={file.url} target="_blank" rel="noreferrer">{file.filename}</a></span>
            ))}
          </p>
          <div className="admin-section-actions">
            <button className="btn secondary" type="button" onClick={() => toggleDetail(snapshot)}>{detail?.snapshot.id === snapshot.id ? "상세 닫기" : "변경 상세"}</button>
            {snapshot.reviewStatus === "pending" && (
              <>
                <button className="btn secondary" type="button" disabled={workingId === snapshot.id} onClick={() => reject(snapshot)}>반려</button>
                <button className="btn primary" type="button" disabled={workingId === snapshot.id} onClick={() => approve(snapshot)}>카탈로그 승인</button>
              </>
            )}
          </div>
          {detail?.snapshot.id === snapshot.id && (
            <div className="admin-muted">
              <p>추가 {detail.addedTotal}: {detail.added.map((item) => `${item.displayName}(${item.jurisdictionName})`).join(", ") || "없음"}</p>
              <p>삭제 {detail.removedTotal}: {detail.removed.map((item) => `${item.displayName}(${item.jurisdictionName})`).join(", ") || "없음"}</p>
              <p>유지 {detail.unchangedTotal}곳{detail.unchangedTotal > detail.unchanged.length ? ` (처음 ${detail.unchanged.length}곳만 조회)` : ""}</p>
            </div>
          )}
        </article>
      ))}{snapshots.length === 0 && <p className="admin-empty">대상 섬 목록 갱신 후보가 없습니다.</p>}</div>
    </section>
  );
}
