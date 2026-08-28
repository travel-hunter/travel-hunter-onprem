# Jenkins 파이프라인에 테스트 단계 추가

**목표:** 배포 전에 백엔드 테스트를 돌려, 깨진 코드가 개발서버에 올라가지 않게 한다.

**범위:** `deploy/jenkins/dev/Jenkinsfile` 한 파일. **개발서버는 건드리지 않는다** — 저장소 파일만 고치고, 반영은 Codex/팀이 한다.

---

## 배경 — 지금 CI에는 테스트가 하나도 없다

`deploy/jenkins/dev/Jenkinsfile` (210줄) 전체 단계:

```
Notify Build start → Check Environment → Pull Latest Code
→ Build and Deploy → Run DB Migration → Check Containers → Health Check
```

검색 결과 `vitest` 0건, `pytest` 0건, `playwright` 0건, `tsc` 0건, `npm test` 0건.

**배포 전용 파이프라인이다.** 그래서 E2E 12개가 몇 달째 안 돌며 낡았고, 이번에 새로 만든 드래그 테스트도 그대로 두면 같은 길을 간다.

---

## 실행 환경 제약 (실측)

`agent { label 'dev' }`, `PROJECT_DIR = /home/deploy/travel-hunter-onprem`.

`Check Environment` 단계가 확인하는 도구는 **`git`, `docker`, `docker compose` 뿐이다.** 호스트에 node·python이 있다는 근거가 없다. 따라서 테스트는 전부 컨테이너 안에서 돌려야 한다.

| 검사 | 실행 가능성 |
|---|---|
| `tsc` | **이미 강제되고 있다.** `frontend/Dockerfile`의 build 스테이지가 `npm run build`를 돌고, 그 스크립트가 `npm run typecheck && vite build`다. 타입 오류가 있으면 이미지 빌드가 실패한다 |
| `pytest` | **가능.** `pytest>=8.3`이 `backend/requirements.txt`에 있어 백엔드 이미지에 설치돼 있다 |
| `vitest` | **지금은 불가.** `npm test`가 `run-backend-command.cjs`를 타는데, 이 스크립트가 **호스트의 python**으로 alembic·seed·uvicorn을 띄운다 (`:153,158,166`). 컨테이너용 러너가 따로 필요하다 |
| Playwright E2E | **지금은 불가.** 같은 이유 + 브라우저 바이너리 필요 |

**따라서 이번 작업은 pytest 하나만 붙인다.** vitest와 E2E는 러너를 컨테이너용으로 고치는 별도 작업이 선행돼야 한다.

---

## 컨테이너에서 pytest 돌리는 법 (실측으로 확정)

`backend/Dockerfile`은 `alembic`, `app`, `scripts`만 복사하고 **`tests`는 이미지에 넣지 않는다.** 그래서 체크아웃된 소스를 마운트해야 한다.

마운트 위치를 세 가지로 시도한 결과:

| 마운트 | 결과 | 원인 |
|---|---|---|
| `backend:/src`, `-w /src` | **11 failed** | `test_timezone_migration_guardrails.py`가 `Path(__file__).parents[N]`로 경로를 계산해 `/backend/alembic/...`을 찾는다. 마운트 위치 때문에 생긴 인공물이지 실제 실패가 아니다 |
| `backend:/repo/backend`, `-w /repo/backend` | 1 failed | `test_agreement_versions_match_frontend_contract`가 프론트 파일을 읽는다. 백엔드만 마운트해서 못 찾는다 |
| **`.:/repo`, `-w /repo/backend`** | **679 passed / 0 failed / 18 skipped** | ✅ |

**저장소 전체를 마운트해야 한다.** 테스트들이 저장소 레이아웃을 전제로 경로를 계산하기 때문이다.

> 참고: 로컬 Windows 호스트에서는 `test_restricted_atomic_artifact_and_sidecar_round_trip` 1건이 실패한다. 임시 디렉터리 권한이 `S_IMODE & 0o077` 검사를 통과하지 못하는 Windows 환경 문제이며, **리눅스 컨테이너에서는 통과한다** — 위 679 passed 에 포함돼 있다.

---

## 단계를 어디에 넣는가

**`Build and Deploy` 앞이다.** 뒤에 두면 깨진 코드를 배포한 다음에 알게 된다.

```
Notify → Check Environment → Pull Latest Code
       → [신규] Backend Tests          ← 여기
       → Build and Deploy → Run DB Migration → Check Containers → Health Check
```

`Pull Latest Code` 다음이어야 한다. 그래야 방금 받은 코드를 검사한다.

### 이미지가 없는 첫 실행 문제

테스트는 `travel-hunter-onprem-backend` 이미지를 쓰는데, 첫 배포 전에는 그 이미지가 없을 수 있다. `Build and Deploy` 앞에 두므로 이전 배포의 이미지를 쓰게 된다 — **의존성이 바뀐 커밋에서는 옛 이미지로 테스트하는 셈**이다.

그래서 테스트 단계에서 백엔드 이미지를 먼저 빌드한다. compose 캐시가 있어 대부분의 커밋에서는 거의 즉시 끝나고, `requirements.txt`가 바뀐 커밋에서만 실제로 다시 빌드된다.

---

## Task 1: Backend Tests 단계 추가

**파일**
- 수정: `deploy/jenkins/dev/Jenkinsfile`

- [ ] **Step 1: `Pull Latest Code` 와 `Build and Deploy` 사이에 삽입**

```groovy
        stage('Backend Tests') {
            steps {
                sh '''
                    echo "===== 백엔드 테스트 ====="
                    cd ${PROJECT_DIR}

                    # 배포 전에 검사한다. 이미지가 옛 의존성일 수 있으므로 먼저 빌드한다.
                    # requirements.txt 가 그대로면 캐시가 걸려 거의 즉시 끝난다.
                    docker compose \\
                      --env-file ${ENV_FILE} \\
                      -f ${COMPOSE_FILE} \\
                      build backend

                    # tests/ 는 이미지에 없다. 저장소 전체를 마운트해야 한다 —
                    # 일부 테스트가 저장소 레이아웃을 전제로 경로를 계산한다.
                    docker compose \\
                      --env-file ${ENV_FILE} \\
                      -f ${COMPOSE_FILE} \\
                      run --rm --no-deps \\
                      -v ${PROJECT_DIR}:/repo \\
                      -w /repo/backend \\
                      backend python -m pytest tests -q
                '''
            }
        }
```

`--no-deps`를 붙여 db 컨테이너를 건드리지 않는다. 백엔드 테스트는 SQLite 인메모리 픽스처를 쓰므로 PostgreSQL이 필요 없다 (`test_policy_source_audit.py`의 `sqlite_db_session` 참조). PostgreSQL이 필요한 테스트는 환경변수로 게이트돼 skip 된다.

- [ ] **Step 2: 실패 시 배포가 멈추는지 확인**

Jenkins `sh`는 종료 코드가 0이 아니면 스테이지를 실패시키고, 기본 설정에서 후속 스테이지는 실행되지 않는다. `pytest`는 실패 시 0이 아닌 코드를 반환한다. **별도 설정이 필요 없다.**

다만 실제로 그런지는 파이프라인을 돌려봐야 안다. Codex/팀이 반영할 때 **일부러 실패하는 테스트를 넣어 배포가 멈추는지 한 번 확인**하기를 권한다. 이 확인 없이 "붙였다"고 넘기면 안 된다.

- [ ] **Step 3: Slack 실패 알림 확인**

`post` 블록이 실패를 Slack에 알리는지 확인한다. 없으면 추가한다 — 알림 없이 조용히 실패하면 붙인 의미가 없다.

- [ ] **Step 4: 커밋**

```bash
git add deploy/jenkins/dev/Jenkinsfile
git commit -m "Run backend tests before deploying in the dev pipeline"
```

---

## 검증

**로컬에서 컨테이너 실행이 되는지는 이미 확인했다.**

```bash
docker run --rm -v "<repo>:/repo" -w /repo/backend travel-hunter-onprem-backend \
  python -m pytest tests -q
# 679 passed, 18 skipped
```

**파이프라인 자체는 로컬에서 검증할 수 없다.** Jenkins 에이전트가 개발서버에 있고 그건 조작 금지 대상이다. 따라서:

- Jenkinsfile 문법은 눈으로 검토한다 (Groovy 파서를 로컬에서 돌릴 수 없다)
- 실제 동작 확인은 **Codex/팀이 반영 후** 수행한다
- 인계 텍스트에 "일부러 실패시켜 배포 차단을 확인할 것"을 명시한다

---

## 후속 작업 (이번 범위 밖)

1. **vitest를 CI에 붙이기** — `run-backend-command.cjs`가 호스트 python을 요구한다. 컨테이너 안에서 백엔드를 띄우는 러너로 바꿔야 한다
2. **Playwright E2E를 CI에 붙이기** — 위 + 브라우저 바이너리. `mcr.microsoft.com/playwright` 이미지를 쓰는 방향
3. **옛 `backend-mode.spec.ts` 낡음 3건** — 정책 URL / 초대 문구 / 장소 수동 입력. 뒤 둘은 "의도된 제거인가 유실인가" 판단 필요
4. **릴리스 체크리스트(`09-release-checklist.md:143`)의 e2e evidence 요구** — 1·2가 끝나야 자동으로 채워진다

---

## 하지 않을 것

- 개발서버 조작 (Jenkins 설정 변경, 파이프라인 실행, 배포)
- `backend/Dockerfile`에 `COPY tests` 추가 — 운영 이미지를 불필요하게 키운다. 마운트로 충분하다
- vitest / E2E 단계 추가 — 러너 수정이 선행돼야 한다
- 옛 E2E 스펙 수정
- push / PR / merge
