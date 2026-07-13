# Travel Hunter

> 흩어진 국내 여행 지원 정책을 발견하고, 실제 여행 일정과 연결해 "혜택을 신청하는 행동"까지 이어주는 여행 지원 플랫폼

![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-psycopg3-4169E1?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-Vitest%20%7C%20Playwright%20%7C%20Pytest-blue)

<!-- 데모 GIF나 메인 화면 스크린샷을 여기에 넣어주세요. 가능하면 3~5초짜리 GIF가 가장 효과적입니다. -->
<p align="center">
  <img src="docs/images/hero.png" alt="Travel Hunter main preview" width="80%"/>
</p>

### 🔗 Quick Links

- 🌐 **Live Demo** · [travel-hunter.example.com](https://travel-hunter.example.com)
- 🎥 **Demo Video** · [YouTube](https://youtu.be/your-demo)
- 📑 **Presentation** · [발표 자료](https://your-deck-link)
- 📖 **API Docs** · [Swagger UI](https://travel-hunter.example.com/docs)

---

## 👥 Team

| 이름 | 역할 | 주요 담당 | GitHub |
|---|---|---|---|
| 이름1 | Frontend Lead | 정책/일정 UI, drag-and-drop, draft autosave | [@github](https://github.com/) |
| 이름2 | Backend Lead | 인증·세션, 권한 모델, Alembic migration | [@github](https://github.com/) |
| 이름3 | Backend | 알림 scheduler/provider/webhook 흐름 | [@github](https://github.com/) |
| 이름4 | Frontend | 협업 초대, 추천 UI, AppDataApi 경계 설계 | [@github](https://github.com/) |
| 이름5 | Infra | Docker Compose, Caddy, Cloudflare Tunnel, CI/CD | [@github](https://github.com/) |

> 본 프로젝트는 N개월간 N명이 함께 진행한 팀 프로젝트입니다.

---

## 📌 Overview

Travel Hunter는 정부와 지자체에 흩어진 국내 여행 지원 정책을 사용자의 여행 계획 안에서 활용할 수 있게 만든 웹 애플리케이션입니다. 정책 탐색, 저장, 일정 연결, 친구 협업을 하나의 흐름으로 묶어 **"혜택을 찾는 것"에서 끝나지 않고 "신청을 준비하는 일정"** 까지 이어지도록 설계했습니다.

React/Vite 프론트엔드와 FastAPI 백엔드, PostgreSQL 데이터베이스로 구성되어 있으며, 정책·인증·일정·협업·알림 흐름 전반이 DB-backed 동작으로 통합되어 있습니다.

## 🎯 Problem & Solution

### Problem

국내 여행 지원 정책은 교통비, 숙박, 지역 화폐, 체험 할인처럼 혜택 유형이 다양하지만 정보가 여러 기관과 지자체에 분산되어 있습니다. 사용자는 조건에 맞는 정책을 찾기 어렵고, 찾더라도 여행 일정과 신청 마감일을 함께 관리하지 못해 **실제 혜택으로 이어지지 않는 경우**가 많습니다.

### Solution

Travel Hunter는 정책 탐색과 여행 일정 관리를 같은 사용자 여정 안에 배치합니다.

- 조건에 맞는 정책을 찾고 저장한 뒤, 특정 여행 일정에 정책을 연결합니다.
- 일정 안에서 장소를 추가·정렬하고, 추천 후보를 일정 장소로 반영합니다.
- 초대 링크를 통해 친구와 viewer/editor 권한으로 협업합니다.
- 마이페이지에서 저장 정책·연결 정책·프로필을 한 화면에서 관리합니다.
- 연락처/OTP/알림 설정 화면과 provider 발송 runtime은 제거됐으며, `notification_deliveries`는 과거 이력용 inert history로만 유지합니다.

---

## ✨ Core Features

**정책 탐색과 저장**

- 정책 목록/상세, 검색·지역·카테고리 필터, 정책 저장
- 공식 안내/신청 링크 분리와 일정 연결 진입점

**인증과 프로필**

- 이메일 회원가입·로그인, refresh cookie 세션, 비밀번호 재설정
- Kakao/Google OAuth 진입점
- 관심 지역·여행 스타일·예산 기반 프로필, 닉네임 추천

**여행 일정**

- 일정 생성/확정, 장소 추가·수정·삭제
- Day 내부 및 Day 간 drag-and-drop 이동
- 일정 생성과 장소 입력 draft autosave 및 복원 안내

**협업과 추천**

- 초대 링크 기반 viewer/editor 권한 부여와 권한별 편집 제한
- 일정 기반 추천 후보 조회와 추천 항목의 일정 장소 추가

**알림 상태**

- 연락처/OTP/마감 알림 설정은 현재 제품/API 계약에서 제거됨
- `notification_deliveries`는 새 발송 row를 만들지 않는 inert history로만 보존

---

## 💡 Key Engineering Decisions

포트폴리오를 보는 분들이 가장 궁금해할 "왜 이렇게 만들었는가"에 대한 기록입니다.

### 1. `AppDataApi` 경계로 프론트엔드 데이터 접근을 한 곳에 모음

페이지가 backend client나 seed data에 직접 결합되면 API 변경 비용이 페이지 전체로 번집니다. 모든 데이터 접근을 `AppDataApi` 단일 경계로 모아, 데이터 소스 교체와 mock 제거 작업이 페이지 수정 없이 진행됐습니다.

### 2. Runtime mock mode 제거, DB-backed로 일원화

초기에는 mock mode와 DB mode가 공존했지만, **두 경로를 모두 유지하는 비용이 기능 추가 비용을 넘어서기 시작**했습니다. 정책·인증·프로필·저장 정책·일정·초대·추천·알림 흐름을 PostgreSQL-backed로 통일해 단일 진실 공급원(single source of truth)을 확보했습니다.

### 3. FastAPI route는 얇게, 책임은 schema/service/repository로 분리

route에 비즈니스 로직이 섞이면 테스트와 재사용이 어렵습니다. request/response shape(`schema`), 비즈니스 로직(`service`), DB 쿼리(`repository`)를 분리해 **권한 검증과 같은 횡단 관심사를 service 계층에서 일관되게 강제**했습니다.

### 4. API는 `camelCase`, DB는 `snake_case`

프론트엔드 계약과 DB 관례를 둘 다 지키기 위해 DTO 변환 지점을 명확히 두었습니다. 양쪽 코드베이스 모두 각자의 관례를 어기지 않게 됩니다.

### 5. Alembic migration을 schema 단일 출처로 사용

`create_all()`에 의존하면 운영 환경 schema가 코드와 어긋날 위험이 있습니다. Alembic migration과 현재 schema 문서를 함께 관리해 schema 변경 이력을 추적 가능하게 만들었습니다.

### 6. 협업 권한을 service 계층에서 강제

UI에서만 버튼을 숨기는 방식은 API 직접 호출로 우회할 수 있습니다. owner/editor/viewer 권한을 service 계층에서 강제해 **UI 제한과 API 권한 검증이 같은 규칙을 따르도록** 했습니다.

### 7. 알림 파이프라인 경계 분리

scheduler / provider / retry / webhook을 분리해, 실제 provider secret 없이도 대상 계산과 delivery 상태 흐름을 단위 테스트로 검증할 수 있게 했습니다.

---

## 🏗 Architecture

```text
React / Vite SPA
        │
        │ AppDataApi
        ▼
FastAPI
  routes ─► schemas ─► services ─► repositories
        │
        │ SQLAlchemy 2.0 + Alembic
        ▼
PostgreSQL

Deployment: Docker Compose + Caddy + Cloudflare Tunnel
```

## 🛠 Tech Stack

| Area | Stack |
|---|---|
| Frontend | React 18, TypeScript 5, Vite 7, React Router 6, `@dnd-kit`, lucide-react |
| Backend | Python, FastAPI, Uvicorn, SQLAlchemy 2.0, Alembic |
| Database | PostgreSQL, psycopg 3 |
| Auth | PyJWT, pwdlib(argon2), refresh token cookie, Kakao/Google OAuth |
| Test | Vitest, Testing Library, Playwright, Pytest, httpx |
| Infra | Docker Compose, Caddy, Cloudflare Tunnel, GitHub Actions, Jenkins CD plan |
