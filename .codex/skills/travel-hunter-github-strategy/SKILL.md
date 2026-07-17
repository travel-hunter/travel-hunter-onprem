---
name: travel-hunter-github-strategy
description: Travel Hunter onprem 저장소의 GitHub 소스 오브 트루스, Semi-Trunk 브랜치, PR, 금지사항을 지키기 위한 로컬 Codex/OMX 작업 가드.
---

# Travel Hunter GitHub 전략 준수 Skill

## 목적

`travel-hunter-onprem`을 GitHub 소스 오브 트루스로 두고, Semi-Trunk 전략을 벗어나는 작업을 막는다.

## 적용 시점

- Travel Hunter onprem 저장소에서 브랜치, 커밋, push, PR을 준비할 때.
- Jenkins dev 통합이나 운영 승격과 연결될 수 있는 변경을 다룰 때.
- secrets/env, backend schema/migration, 배포 문서를 만질 가능성이 있을 때.

## 브랜치 규칙

- `main`: 운영/승격 기준이다. 직접 push하지 않는다.
- `develop`: 테스트·QA·Jenkins dev 통합 기준이다. 직접 push하지 않는다.
- `feature/*`: 실제 작업 브랜치다. 항상 최신 `origin/develop`에서 분기한다.
- PR은 기본적으로 `feature/*` → `develop`으로 만든다.
- PR merge와 운영 승격은 사용자가 별도로 지시하고, 필요한 리뷰/검증이 끝난 뒤에만 진행한다.

## 작업 절차

1. `git remote -v`로 origin이 `https://github.com/travel-hunter/travel-hunter-onprem.git`인지 확인한다.
2. `git fetch origin`으로 원격 상태를 갱신한다.
3. `main` 또는 `develop` 위에서 직접 작업하지 않는다.
4. `git checkout -B feature/<작업명> origin/develop`로 feature 브랜치를 만든다.
5. 변경 전 `git status --short`와 `git diff --stat`으로 unrelated dirty work를 분리한다.
6. 포함 범위만 staged한다. backend 정책/데이터/schema/migration 변경은 명시 범위가 아니면 제외한다.
7. 검증 명령과 제외 범위 증거를 PR 본문에 남긴다.
8. `git push -u origin feature/<작업명>`로 feature 브랜치만 push한다.
9. PR은 `develop` 대상으로 만들고, 기본은 Draft PR로 생성한다.

## 금지사항

- `main` 직접 업데이트 금지.
- `develop` 직접 push 금지.
- `git push --force` 금지. 필요한 경우에도 `--force-with-lease`만 검토한다.
- PR merge 금지.
- 운영 승격 금지.
- `.env`, provider secret, tunnel token, DB password, auth secret 커밋 금지.
- 사용자가 제외한 backend 정책/데이터/schema/migration 변경 커밋 금지.
- 현재 작업과 무관한 dirty work를 함께 커밋 금지.

## 산출물 기준

최종 보고에는 반드시 다음을 포함한다.

- 클론 경로
- 브랜치
- 커밋 SHA
- PR URL
- 변경 파일 목록
- 검증 명령 결과
- 제외 파일이 diff에 없다는 증거
