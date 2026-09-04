# 마감 지난 정책이 정책 탭에 계속 노출되는 원인 조사

- **조사일**: 2026-09-02
- **증상**: 마감일이 지난 정책이 `/policies`에 계속 표시됨
- **확인 환경**: 로컬 테스트 서버 `:5173` (Vite dev) + backend `:8000` + db `:55432`
- **성격**: 읽기 전용 조사. 코드/데이터 변경 없음.

---

## 결론

만료 처리는 **조회 시점 날짜 비교가 아니라 수집 파이프라인에서 `status`를 내리는 구조**로 설계돼 있다. 그 판정이 크롤러가 돌 때만 일어나므로, 수집이 멈추면 마감이 지나도 정책이 내려갈 경로가 없다.

`docs/screen-feature-status-logic.md:30`

> 만료/비활성 처리 | 완료 | 공개 승격 대상이 아닌 마감/unknown/stale 및 legacy source 연결 정책을 `hidden` 상태로 숨긴다.

---

## 설계된 파이프라인 (4단계)

| 단계 | 위치 | 동작 |
|---|---|---|
| 1. 상태 판정 | `backend/app/services/travelmonth_normalizer.py:143` `normalize_status()` | 문구("종료"/"마감") 또는 **`today > end_date`** → `"ended"` |
| 2. 신선도 기록 | `backend/app/services/travelmonth_parser.py:562` `_freshness_status()` | `ended` → `"expired"`, `active` → `"fresh"`, 나머지 → `"unknown"` |
| 3. 승격 차단 | `backend/app/repositories/external_sources.py:111, 248, 275` | `freshness_status == "fresh"` 인 레코드만 승격 |
| 4. 강등 | `backend/app/repositories/external_sources.py:131` `list_policy_deactivation_records()` → `backend/app/services/policy_normalization.py:533` `_hide_policy_for_external_record()` | 공개 조건 탈락 레코드의 정책을 `status = "hidden"` |

최종 노출 필터는 하나뿐이다.

```python
# backend/app/repositories/policies.py:8
def _active_policy_clause():
    return Policy.status == POLICY_STATUS_ACTIVE
```

`Policy.status`는 `active` / `hidden` 2종뿐이고 `expired` 상태는 존재하지 않는다 (`backend/app/models/policy_status.py:5-10`, DB에도 `ck_policies_status_active_hidden` 체크 제약).

---

## 왜 지금 안 내려가나

### 1. 만료 판정이 수집 시점에만 일어난다

`normalize_status(status_text, start_date, end_date, today)`의 `today`는 **크롤러 실행 시점에 주입되는 값**이다. 레코드가 한 번 `fresh`로 굳으면, 이후 실제 날짜가 마감일을 넘겨도 재평가하는 주체가 없다.

### 2. 조회 경로에 방어가 없다

- **백엔드**: `list_policies()`(`services/policies.py:241`)는 `policy_repository.list_policies(db)`에 그대로 위임하고, 그 쿼리의 조건은 `Policy.status == 'active'` 하나뿐이다. `end_date` 비교 없음.
- **프론트**: `PolicyPages.tsx:133` `matchesPeriod()`는 기본값 `"전체"`에서 무조건 `true`를 돌려준다. `7일 이내` / `30일 이내` / `3개월 이내` 필터를 걸어야만 `days >= 0` 조건으로 지난 정책이 빠진다.
- 프론트는 만료를 **인지는 한다** — `utils.ts:23` `formatPolicyDeadlineTag()`가 지난 정책에 "마감" 배지를 붙인다. 표시만 하고 목록에서 제외하지는 않는다.

### 3. 수집 스케줄러가 꺼져 있다

`.env`: `EXTERNAL_COLLECTION_SCHEDULER_ENABLED=false`

---

## 측정 데이터 (2026-09-02 기준)

```
policies                     active 92 / hidden 17
active 92건 중 end_date < 오늘 →  87건   (대부분 2026-08-31, 숙박세일 페스타)
그 87건의 verification_status →  전부 'fresh'

external_source_records
  fresh   / active     54
  unknown / ended       9
  unknown / scheduled   2
  expired / *           0      ← expired 레코드가 하나도 없음
```

`:5173` 화면 실측: 정책 카드 **92개** (DB active 수와 정확히 일치), `D-n` 표기 **0개**, 카드마다 "마감" 배지.

```
🛏️ | 최대 7만원 | 마감 | [강진] 2026 대한민국 숙박세일 페스타 숙박 할인
📍 | 전남 · 2026.06.11 시작 · 2026.08.31 마감
```

---

## 곁가지 발견: `expired`와 `unknown`이 구분되지 않는다

숙박할인 파서는 `expired`를 **아예 만들지 않는다**.

```python
# backend/app/services/travelmonth_stay_parser.py:349
freshness_status="fresh" if status == "active" else "unknown",
```

`ended`도 `unknown`으로 뭉개진다. 승격 필터가 `fresh`만 통과시키므로 노출 결과는 같지만, **"마감돼서 내려감"과 "수집이 실패해서 상태를 모름"이 데이터상 구분되지 않는다.** 같은 패턴이 `travelmonth_traffic_parser.py:153`, `dgtourcard_parser.py:357`에도 있다. `expired`를 실제로 기록하는 곳은 `travelmonth_parser.py:562` 하나뿐이다.

이는 기존에 파악된 "수집 실패 시 낡은 정책이 안 내려간다" 이슈와 뿌리가 같다 — 강등이 전적으로 수집 성공에 의존한다.

---

## 개선 방향 (미결정)

성격이 다른 두 갈래다.

### (a) 조회 시점 방어

목록 쿼리 또는 프론트에서 `end_date < today`를 제외한다.

- 장점: 수집 상태와 무관하게 즉시 효과. 수집이 며칠 멈춰도 화면은 정상.
- 단점: 노출 여부의 진실원이 `status`와 `end_date` 둘로 갈린다. 관리자가 `status`로 제어하던 것과 어긋날 수 있고, `end_date`가 null이거나 "예산 소진 시 조기 종료" 같은 케이스는 여전히 못 잡는다.

### (b) 수집 / 정합성 복구

스케줄러를 켜거나, 수집과 분리된 reconciliation 잡을 두고 날짜 경과분을 주기적으로 `hidden` 처리한다.

- 장점: 원 설계와 일관. 진실원이 `status` 하나로 유지된다.
- 단점: 수집 파이프라인 신뢰도가 전제. 위 "곁가지 발견"대로 실패와 만료가 구분되지 않는 문제를 먼저 풀어야 안전하다. 수집이 깨진 채 reconciliation만 돌면 멀쩡한 정책까지 내려갈 위험이 있다.

두 방향을 섞는 절충(조회 시점 방어를 안전망으로 두고 reconciliation을 본 해법으로 진행)도 가능하다.

---

## 조사에 쓴 확인 명령

```bash
# 만료됐지만 노출 중인 정책
docker exec travel-hunter-onprem-db-1 psql -U travelhunter -d travelhunter -c \
  "select count(*) from policies where status='active' and end_date < current_date;"

# 소스 레코드 신선도 분포
docker exec travel-hunter-onprem-db-1 psql -U travelhunter -d travelhunter -c \
  "select freshness_status, status, count(*) from external_source_records group by 1,2;"
```
