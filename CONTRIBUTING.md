# 트래블헌터 앱 기여 가이드

> 이 문서는 `travel-hunter-app` 레포에 처음 기여하는 팀원을 위한 안내서입니다.
> 스터디 레포(`travel-hunter-study`)의 PR 흐름을 먼저 익히고 오세요.

---

## 목차

1. [브랜치 전략](#1-브랜치-전략)
2. [커밋 메시지 규칙](#2-커밋-메시지-규칙)
3. [기여 흐름](#3-기여-흐름)
4. [PR 규칙](#4-pr-규칙)
5. [MVP RC 참고 문서](#5-mvp-rc-참고-문서)
6. [검증 명령](#6-검증-명령)
7. [Secret 규칙](#7-secret-규칙)
8. [자주 하는 실수](#8-자주-하는-실수)

---

## 1. 브랜치 전략

```text
main             # 최종 배포 브랜치, PR + 리뷰 1명 필수
develop          # 개발 통합 브랜치, PR 필수
feature/기능명   # 기능 개발
fix/버그명       # 버그 수정
docs/문서명      # 문서 작업
infra/작업명     # 인프라 작업
```

브랜치 흐름:

```text
feature/기능명
      ↓ PR
develop (통합 테스트)
      ↓ PR + 리뷰 1명
main (배포)
```

`main`, `develop`에 직접 푸시하지 않는다. 반드시 PR을 통해서만 머지한다.

현재 MVP RC 검토 브랜치:

```text
feat/prototype-to-react
```

---

## 2. 커밋 메시지 규칙

```text
type: 작업 내용 요약
```

예시:

```text
feat: 카카오 소셜 로그인 구현
fix: JWT 토큰 만료 오류 수정
docs: API 명세서 업데이트
infra: Terraform VPC 모듈 추가
ci: GitHub Actions 배포 파이프라인 구성
```

| type | 사용 상황 |
| --- | --- |
| `feat` | 새 기능 추가 |
| `fix` | 버그 수정 |
| `docs` | 문서 수정 |
| `style` | 코드 포맷 변경 |
| `refactor` | 코드 리팩토링 |
| `test` | 테스트 추가/수정 |
| `infra` | 인프라 코드 변경 |
| `ci` | CI/CD 설정 변경 |
| `chore` | 빌드, 설정, 유지보수 작업 |

---

## 3. 기여 흐름

새 기능 개발 시:

1. `develop` 기준으로 새 브랜치를 만든다.
2. 작업 후 목적 단위로 커밋한다.
3. `develop`으로 PR을 생성한다.
4. PR에서 변경 내용, 검증 결과, 남은 리스크를 적는다.
5. PR 머지 후 브랜치를 삭제한다.
6. `develop` → `main` PR은 배포 준비가 됐을 때 팀장이 관리한다.

브랜치 이름 예시:

```text
feature/kakao-login
feature/travel-policy-api
fix/jwt-token-expiry
docs/api-spec-update
infra/terraform-vpc
```

---

## 4. PR 규칙

PR 제목:

```text
type: 작업 내용 요약
```

PR 본문에는 다음을 포함한다.

- 변경 내용
- 변경 이유
- 영향 범위
- 실행한 검증 명령
- 관련 문서 업데이트 여부
- 남은 리스크 또는 후속 작업
- UI 변경 시 스크린샷

PR 규칙 요약:

| 브랜치 | 리뷰어 | 머지 방식 |
| --- | --- | --- |
| `feature/*` → `develop` | 없어도 OK | Create a merge commit |
| `fix/*` → `develop` | 없어도 OK | Create a merge commit |
| `docs/*` → `develop` | 없어도 OK | Create a merge commit |
| `develop` → `main` | 1명 필수 | Create a merge commit |

API shape가 바뀌면 `docs/mvp-api-contract.md`, frontend type, backend schema/service/test, `.agent/evals`를 함께 갱신한다.

DB schema는 Alembic migration으로만 변경한다. SQLAlchemy `create_all()`은 사용하지 않는다.

---

## 5. MVP RC 참고 문서

처음 참여하는 개발자는 아래 순서로 읽는다.

1. `README.md`
2. `docs/requirements.md`
3. `docs/implemented-feature-spec.md`
4. `docs/next-work-plan.md`
5. `docs/specs/spec-index.md`
6. `docs/mvp-api-contract.md`
7. `docs/db-schema-current.md`
8. `docs/deployment-cicd/README.md`

현재 MVP는 FastAPI + PostgreSQL DB-backed-only 기준이다. runtime mock mode는 제거됐다.

새 참여자는 `feat/prototype-to-react` 브랜치에서 현재 RC 상태를 검토하고, 다음 개발은 `develop`에 머지된 뒤 새 작업 브랜치에서 시작한다.

---

## 6. 검증 명령

기본 검증:

```bash
cd frontend
npm run typecheck
npm test

cd ../backend
python -m pytest
```

릴리즈 후보 검증:

```bash
cd frontend
npm run test:e2e
npm run build

cd ..
docker compose -f compose.yaml config
docker compose -f compose.yaml build
docker compose -f compose.yaml run --rm backend alembic upgrade head
docker compose -f compose.yaml run --rm backend python -m app.db.seed
docker compose --env-file deploy/.env.tunnel.example -f compose.tunnel.yaml config
```

---

## 7. Secret 규칙

- `.env`, 실제 배포 env, DB password, `AUTH_SECRET_KEY`, SSH 정보, tunnel token은 커밋하지 않는다.
- repo에는 예시 파일만 둔다: `deploy/.env.tunnel.example`.
- 실제 staging 값은 GitHub 문서가 아니라 별도 비밀 공유 수단으로 전달한다.

---

## 8. 자주 하는 실수

| 실수 | 해결 방법 |
| --- | --- |
| main 기준으로 브랜치 만들었어요 | 브랜치 삭제 후 develop 기준으로 다시 생성 |
| develop에 직접 푸시하려 했어요 | PR로만 머지 가능, 새 브랜치에서 작업 |
| PR base를 main으로 했어요 | PR 편집에서 base를 develop으로 변경 |
| 브랜치 삭제를 깜빡했어요 | 레포 → branches에서 삭제 |
| 커밋 메시지 규칙 안 지켰어요 | 다음 커밋부터 규칙을 지킨다 |

---

last updated: 2026-05-07
