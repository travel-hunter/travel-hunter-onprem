# Brevo/Cloudflare 메일 발송 명세서

## 목적

이 문서는 `travel-hunter.co.kr` 도메인에서 비밀번호 재설정 메일을 발송하고 smoke test까지 확인하기 위한 설정 명세다.

적용 범위:

- Cloudflare DNS와 Email Routing 설정
- Brevo SMTP 발송 계정과 도메인 인증 설정
- `no-reply@travel-hunter.co.kr` 발신자 사용
- FastAPI backend의 password reset email 발송 환경변수
- 로컬 또는 staging-like 환경의 비밀번호 재설정 메일 smoke test

Cloudflare Email Routing은 수신 메일 forwarding만 담당한다. 비밀번호 재설정 메일 같은 발신 메일은 Brevo SMTP가 담당한다.

## 현재 구현 전제

- backend는 비밀번호 재설정 요청 시 `backend/app/services/email.py`의 SMTP 발송 경로를 사용한다.
- backend는 `SMTP(...).starttls()`를 사용하므로 SMTP port는 `587`을 기준으로 한다.
- `465` port의 implicit TLS는 현재 backend 구현 경로가 아니므로 사용하지 않는다.
- SMTP 설정이 없으면 기존 구현은 사용자에게 이메일 발송 설정이 없다는 상태를 보여준다.
- 실제 SMTP credential, Cloudflare token, Brevo key, 운영 `.env` 값은 저장소에 커밋하지 않는다.

## 역할 분리

| 구성요소 | 역할 | 비고 |
| --- | --- | --- |
| Cloudflare DNS | `travel-hunter.co.kr` DNS 관리 | Gabia nameserver를 Cloudflare nameserver로 변경해야 한다. |
| Cloudflare Email Routing | 도메인 메일 수신 forwarding | outbound SMTP 발송 기능이 아니다. |
| Brevo SMTP | password reset email 발송 | SMTP credential을 backend env에 주입한다. |
| FastAPI backend | reset token 생성과 메일 발송 요청 | `TRAVEL_HUNTER_PUBLIC_BASE_URL`로 reset link를 만든다. |
| Frontend | `/forgot-password`, `/reset-password?token=...` UX | 사용자는 이메일 링크로 새 비밀번호를 설정한다. |

## 1. Cloudflare 계정 준비

1. 대표자 또는 조직 소유 이메일로 Cloudflare 계정을 생성한다.
2. Cloudflare 계정에 2FA를 활성화한다.
3. 팀 운영이 필요하면 공유 비밀번호 관리 도구에 계정을 등록한다.
4. 추가 운영자는 비밀번호 공유가 아니라 Cloudflare Members로 초대한다.

## 2. Cloudflare에 도메인 추가

1. Cloudflare dashboard를 연다.
2. `Add a website`를 선택한다.
3. `travel-hunter.co.kr`을 입력한다.
4. 별도 유료 요구가 없으면 Free plan을 선택한다.
5. Cloudflare가 기존 DNS record를 scan하도록 둔다.
6. 설정 마지막 단계에서 표시되는 Cloudflare nameserver 2개를 복사한다.

Nameserver 예시 형식:

```text
example-a.ns.cloudflare.com
example-b.ns.cloudflare.com
```

## 3. Gabia nameserver 변경

1. Gabia에 로그인한다.
2. `My Gabia`에서 domain management로 이동한다.
3. `travel-hunter.co.kr`을 선택한다.
4. nameserver 설정을 연다.
5. 기존 nameserver를 Cloudflare에서 제공한 nameserver 2개로 교체한다.
6. 변경사항을 저장한다.

DNS 전파는 수 분에서 수 시간까지 걸릴 수 있다.

## 4. Cloudflare 활성화 확인

1. Cloudflare dashboard로 돌아간다.
2. `travel-hunter.co.kr` 상태가 active가 될 때까지 기다린다.
3. active 이후 DNS record 관리는 Cloudflare에서 수행한다.

## 5. Cloudflare Email Routing 설정

1. Cloudflare에서 `travel-hunter.co.kr` zone을 연다.
2. `Email` 또는 `Email Routing` 메뉴로 이동한다.
3. Email Routing을 활성화한다.
4. forwarding 받을 destination email address를 추가한다.
5. destination verification email을 확인한다.
6. custom address를 추가한다.

권장 custom address:

```text
no-reply@travel-hunter.co.kr
support@travel-hunter.co.kr
```

권장 routing:

```text
no-reply@travel-hunter.co.kr -> representative inbox
support@travel-hunter.co.kr -> representative inbox
```

주의: `no-reply@travel-hunter.co.kr`은 password reset 발신자로도 쓰지만, Cloudflare Email Routing은 수신 forwarding만 처리한다. 실제 발신 인증은 Brevo에서 별도로 완료해야 한다.

## 6. Brevo SMTP 계정 준비

1. Brevo 계정을 생성한다.
2. transactional email 또는 SMTP 영역으로 이동한다.
3. `SMTP and API settings`를 연다.
4. SMTP credential을 생성하거나 기존 credential을 복사한다.

필수 값:

```text
SMTP host: smtp-relay.brevo.com
SMTP port: 587
SMTP login: Brevo SMTP username
SMTP key: Brevo SMTP key
```

`SMTP_PASSWORD`에는 Brevo 웹 로그인 비밀번호가 아니라 Brevo SMTP key를 넣는다.

## 7. Brevo 도메인 인증

1. Brevo에서 `Senders & Domains`를 연다.
2. `travel-hunter.co.kr`을 발신 도메인으로 추가한다.
3. Brevo가 제공하는 DNS record를 복사한다.
4. Cloudflare DNS에 해당 record를 추가한다.

일반적으로 필요한 record:

- DKIM
- DMARC
- Brevo verification code
- Brevo가 요구하는 SPF/TXT record

DNS record를 추가한 뒤 Brevo로 돌아가 domain verification을 실행한다.

완료 조건:

- Brevo에서 `travel-hunter.co.kr` 도메인이 verified 상태다.
- `no-reply@travel-hunter.co.kr`이 Brevo에서 허용된 sender 또는 인증된 도메인 sender로 동작한다.
- Cloudflare DNS에 Brevo 인증 record가 남아 있다.

## 8. 로컬 backend 환경변수

로컬 backend 환경 파일:

```text
backend/.env
```

필수 설정 예시:

```env
TRAVEL_HUNTER_PUBLIC_BASE_URL=http://127.0.0.1:5173
PASSWORD_RESET_EXPIRE_MINUTES=30

SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=<Brevo SMTP login>
SMTP_PASSWORD=<Brevo SMTP key>
SMTP_FROM_EMAIL=no-reply@travel-hunter.co.kr
SMTP_USE_TLS=true
```

backend는 시작 시점에 `backend/.env`를 읽는다. 값을 바꾼 뒤에는 FastAPI backend를 재시작한다.

## 9. staging 또는 tunnel 환경변수

staging 또는 Cloudflare Tunnel smoke test에서는 같은 SMTP 값을 다음 환경 파일에 반영한다.

```text
deploy/.env.staging
deploy/.env.tunnel
```

staging-like 환경의 `TRAVEL_HUNTER_PUBLIC_BASE_URL`은 localhost가 아니라 public HTTPS URL이어야 한다.

예시:

```env
TRAVEL_HUNTER_PUBLIC_BASE_URL=https://travel-hunter.co.kr
SMTP_FROM_EMAIL=no-reply@travel-hunter.co.kr
```

## 10. 비밀번호 재설정 메일 smoke test

사전 조건:

- backend가 Brevo SMTP env를 읽은 상태로 재시작됐다.
- 입력할 email은 DB에 존재하는 사용자 email이다.
- Brevo domain verification이 완료됐다.
- `TRAVEL_HUNTER_PUBLIC_BASE_URL`이 현재 frontend 접근 URL과 일치한다.

화면 기준 절차:

1. backend를 재시작한다.
2. frontend를 연다.
3. `/forgot-password`로 이동한다.
4. 로컬 DB에 존재하는 email을 입력한다.
5. reset email 수신을 확인한다.
6. email 안의 reset link를 연다.
7. `/reset-password?token=...`에서 새 비밀번호를 설정한다.
8. 새 비밀번호로 로그인한다.

API 기준 요청:

```bash
curl -X POST "http://127.0.0.1:8000/api/auth/password-reset/request" \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com"}'
```

성공 기준:

- 존재하지 않는 email에도 계정 존재 여부를 노출하지 않는 동일한 응답을 반환한다.
- 존재하는 email에는 reset email이 실제 수신된다.
- reset link의 token으로 새 비밀번호 설정이 완료된다.
- 기존 비밀번호가 아니라 새 비밀번호로 로그인된다.

## 보안 및 운영 주의사항

- 실제 SMTP credential을 커밋하지 않는다.
- 실제 `.env`, tunnel token, OAuth secret, DB password, SMTP password를 저장소에 추가하지 않는다.
- `SMTP_FROM_EMAIL`은 Brevo에서 인증된 sender 또는 인증된 domain sender와 일치해야 한다.
- Cloudflare Email Routing만 설정했다고 outbound password reset email 발송이 되는 것은 아니다.
- SMTP credential을 교체하면 backend 환경변수와 운영 secret 저장소를 함께 갱신한다.
- staging/public smoke는 도메인, DNS 전파, public HTTPS, Brevo 인증 상태에 의존하므로 로컬 UX 완료 작업과 분리해서 관리한다.
