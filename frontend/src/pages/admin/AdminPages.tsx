import { FormEvent, useEffect, useMemo, useState } from "react";
import { Link, NavLink, Outlet, useNavigate, useParams } from "react-router-dom";
import { appDataApi, type AdminAuditLogListItem, type AdminExternalSourceSummaryResponse, type AdminPolicyDetail, type AdminPolicyListItem, type AdminPolicyStatus, type AdminUserDetail, type AdminUserListItem, type ExternalCollectionOpsHealth, type ExternalCollectionRunResponse } from "../../api";

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
