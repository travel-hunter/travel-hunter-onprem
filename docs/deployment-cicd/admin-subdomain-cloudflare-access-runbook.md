# 관리자 전용 도메인 및 Cloudflare Access 운영 절차

## 범위

- 관리자 화면: `https://admin.travel-hunter.co.kr/admin`
- 일반 개발 화면: `https://dev.travel-hunter.co.kr`
- Cloudflare Access는 관리자 도메인 전체에만 적용한다. Jenkins와 일반 개발 도메인에는 적용하지 않는다.

## Cloudflare 설정

1. Tunnel Published application route의 관리자 호스트는 `admin.travel-hunter.co.kr` → `http://caddy:80`이어야 한다. Caddy 내부 포트 80은 HTTPS가 아니다.
2. Access Application의 Public hostname은 `admin.travel-hunter.co.kr`으로 둔다.
3. Allow 정책은 운영자 이메일 정확 일치(Exact email)와 Cloudflare One-time PIN을 사용한다.
4. Access 허용 목록과 Travel Hunter DB의 `role=admin`은 별개 방어선이다. 운영자 추가와 회수 때 둘 다 처리한다.

## 런타임 환경값

비밀값을 출력하거나 커밋하지 않는다. 운영 환경 파일에는 다음 값을 둔다.

```text
STAGING_DOMAIN=dev.travel-hunter.co.kr
ADMIN_DOMAIN=admin.travel-hunter.co.kr
VITE_API_BASE_URL=same-origin
VITE_ADMIN_BASE_URL=https://admin.travel-hunter.co.kr
CORS_ORIGINS=https://dev.travel-hunter.co.kr,https://admin.travel-hunter.co.kr
```

`TRAVEL_HUNTER_PUBLIC_BASE_URL`과 Google/Kakao OAuth callback URL은 일반 개발 도메인을 유지한다.

## 배포와 확인

1. 일반 도메인과 관리자 도메인 모두 Caddy가 같은 backend/frontend로 프록시하도록 새 이미지를 빌드한다.
2. `backend`, `frontend`, `caddy`를 재기동한다. Tunnel 라우트만 바뀌지 않았다면 `cloudflared` 재기동은 필요 없다.
3. 일반 도메인의 `/admin`이 관리자 도메인의 `/admin`으로 302 이동하는지 확인한다.
4. 허용 이메일은 One-time PIN을 통과하고, 비허용 이메일은 Access에서 차단되는지 확인한다.
5. 관리자 도메인에서는 서버 전용 명령으로 만든 내부 관리자 아이디·비밀번호만 로그인한다. 소셜 로그인·회원가입·비밀번호 재설정 진입점은 노출하지 않는다.
6. 일반 계정이 `/api/admin/*`, `/api/ops/*`에 접근하면 거부되는지 확인한다.

## 내부 관리자 계정 생성

운영 서버에서 컨테이너 안에 들어가 실행한다. 비밀번호는 대화형 입력만 허용하며 명령줄·로그·파일에 넣지 않는다.

```bash
python -m app.scripts.create_internal_admin \
  --email operator-name@travel-hunter.invalid \
  --nickname "운영자 표시명"
```

이미 있는 계정은 생성하지 않는다. 계정 회수는 먼저 Cloudflare Access 허용 목록에서 제거하고, 이후 DB 역할을 제거한다.

## 장애 복구

관리자 도메인만 실패하면 Tunnel route가 `http://caddy:80`인지, Caddy와 frontend의 새 이미지가 기동했는지, 환경 파일에 두 도메인이 모두 있는지 순서대로 확인한다. 긴급 롤백은 이전 이미지와 이전 환경 파일로 backend/frontend/caddy를 함께 재기동한다.