# Travel Hunter Semi-Trunk 브랜치 전략

이 저장소(`travel-hunter-onprem`)는 앞으로 Travel Hunter의 GitHub 소스 오브 트루스다. 모든 팀원과 자동화는 아래 브랜치 경계를 기준으로 작업한다.

## 브랜치 역할

| 브랜치 | 역할 | 규칙 |
|---|---|---|
| `main` | 운영/승격 기준 | 직접 push 금지. 검증된 `develop`만 운영 승격 절차로 반영한다. |
| `develop` | 테스트·QA·Jenkins dev 통합 기준 | 직접 push 금지. 모든 기능/수정은 PR로만 합류한다. |
| `feature/*` | 개별 작업 브랜치 | `develop`에서 분기하고, `develop` 대상 PR로 검토한다. |

## 기본 흐름

1. 최신 원격 상태를 받는다.
   ```bash
   git fetch origin
   ```
2. `develop` 기준으로 작업 브랜치를 만든다.
   ```bash
   git checkout -B feature/<작업명> origin/develop
   ```
3. 범위가 작은 커밋으로 작업하고 로컬 검증을 남긴다.
4. feature 브랜치만 원격에 push한다.
   ```bash
   git push -u origin feature/<작업명>
   ```
5. GitHub에서 `feature/<작업명>` → `develop` PR을 만든다.
6. PR 리뷰와 CI/Jenkins dev 검증이 끝나기 전에는 merge하지 않는다.
7. `main` 승격은 별도 운영 릴리스 절차로만 진행한다.

## 금지사항

- `main` 직접 push 금지.
- `develop` 직접 push 금지.
- feature 브랜치에서 PR 없이 운영 승격 금지.
- PR 작성자가 임의로 merge하거나 운영 배포까지 진행 금지.
- `.env`, provider secret, tunnel token, DB password, auth secret 등 민감 정보 커밋 금지.
- 범위 밖 backend 정책/데이터/schema/migration 변경을 feature PR에 섞지 않는다.

## 이번 첫 onprem 작업 브랜치

- 브랜치: `feature/signup-verify-state-fix`
- 기준 브랜치: `origin/develop`
- PR 대상: `develop`
- 포함 범위:
  - signup verify 프론트 상태 수정
  - 해당 회귀 테스트
  - Semi-Trunk 전략 문서/가드
  - 프로젝트 로컬 Codex/OMX skill
- 제외 범위:
  - backend 정책/데이터/schema/migration 변경
  - secrets/env 변경
  - `main` 업데이트
  - PR merge 또는 운영 승격
  - 기존 unrelated dirty work
