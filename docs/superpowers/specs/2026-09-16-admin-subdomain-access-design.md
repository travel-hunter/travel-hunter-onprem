# 관리자 전용 서브도메인 접근 설계

## 목표

일반 서비스와 내부 운영자 화면을 호스트 수준에서 분리하고, Cloudflare Access와 앱의 관리자 역할을 함께 요구한다.

## 호스트 경계

| 환경 | 일반 서비스 | 관리자 서비스 |
| --- | --- | --- |
| 개발 | `dev.travel-hunter.co.kr` | `admin.travel-hunter.co.kr` |
| 운영 | `travel-hunter.co.kr` | `admin.travel-hunter.co.kr` |

관리자 호스트의 루트는 `/admin`으로 이동한다. 일반 서비스 호스트의 `/admin`은 관리자 호스트로 이동한다. 관리자 API는 기존 `/api/admin/*`, 수집 운영 API는 `/api/ops/*`를 유지한다.

## 접근 제어

1. Cloudflare Access가 관리자 호스트 전체를 Cloudflare One-time PIN 로그인과 허용 이메일 목록으로 보호한다.
2. Access 통과 후에도 Travel Hunter 세션과 `users.role = 'admin'`이 필요하다.
3. 일반 호스트에는 Access를 적용하지 않는다. GitHub webhook 등 기계 경로는 관리자 호스트에 두지 않는다.
4. 관리자 세션 쿠키는 호스트 전용으로 유지한다. 일반 사용자 도메인과 공유하지 않는다.

## 배포와 실패 동작

Caddy는 두 host block을 명시적으로 분리한다. 관리자 호스트는 같은 frontend/backend 서비스를 프록시하지만 별도 host header를 가진다. 관리 도메인, CORS origin, OAuth redirect URI, Cloudflare Tunnel public hostname은 환경별 runtime 설정으로 관리하고 비밀값은 저장소에 넣지 않는다.

Cloudflare Access가 비활성·오구성되더라도 backend `require_admin_user`는 계속 최종 권한 경계로 작동한다. 일반 호스트에서 `/admin`을 직접 열어도 관리 UI가 노출되지 않아야 한다.

## 검증 기준

- 일반 호스트 `/admin`은 관리자 호스트 `/admin`으로 이동한다.
- 관리자 호스트 `/`는 `/admin`으로 이동한다.
- 일반 사용자·비로그인 사용자·Access만 통과한 비관리자 계정은 `/api/admin/*`에서 거부된다.
- 관리자 계정은 관리자 호스트에서 정책 수집·후보 승인 화면을 사용할 수 있다.
- GitHub webhook은 관리자 Access 정책의 대상이 아니다.
