# Travel Hunter 도메인/메일/터널링 초보 가이드

대상 도메인: `travel-hunter.co.kr`

이 문서는 지금까지 진행한 일을 아주 쉽게 다시 정리하고, 다음 단계인 Cloudflare Tunnel을 누구나 따라할 수 있게 설명한다.

공식 문서 참고:

- Cloudflare Tunnel 개요: https://developers.cloudflare.com/tunnel/
- Cloudflare Tunnel 설정: https://developers.cloudflare.com/tunnel/setup/
- Cloudflare Tunnel 라우팅: https://developers.cloudflare.com/tunnel/routing/

---

## 1. 지금까지 한 일을 아주 쉽게 이해하기

우리가 연결한 것은 크게 3개다.

```text
Gabia = 도메인을 산 곳
Cloudflare = 도메인 주소와 DNS를 관리하는 곳
Brevo = 이메일을 보내주는 곳
```

조금 더 쉽게 말하면 다음과 같다.

```text
Gabia
= travel-hunter.co.kr 이름표를 산 문방구

Cloudflare
= 그 이름표가 어디로 가야 하는지 알려주는 안내 데스크

Brevo
= 사용자에게 이메일을 보내주는 우체국
```

---

## 2. 지금까지 완료한 것

현재 완료된 것으로 보이는 항목은 다음과 같다.

```text
1. Gabia에서 travel-hunter.co.kr 도메인을 구매했다.
2. Gabia nameserver를 Cloudflare nameserver로 바꿨다.
3. Cloudflare에서 travel-hunter.co.kr 도메인이 Active 상태가 됐다.
4. Brevo에서 travel-hunter.co.kr 도메인 인증용 DNS 값을 받았다.
5. Brevo가 준 DNS 값을 Cloudflare DNS에 추가했다.
6. Brevo sender에 no-reply@travel-hunter.co.kr를 추가했다.
7. no-reply@travel-hunter.co.kr sender가 Verified 상태가 됐다.
8. DKIM과 DMARC도 Brevo 화면에서 정상으로 보인다.
```

이 상태라면, 외부 서비스 연결의 큰 틀은 잘 끝난 것이다.

---

## 3. 각 서비스가 맡는 역할

헷갈릴 때는 아래 표만 보면 된다.

| 서비스 | 역할 | 쉽게 말하면 |
| --- | --- | --- |
| Gabia | 도메인 구매 | 이름표를 산 곳 |
| Cloudflare | DNS 관리 | 주소 안내 데스크 |
| Cloudflare Email Routing | 메일 수신 전달 | no-reply로 온 메일을 내 Gmail로 보내줌 |
| Brevo | 메일 발송 | 비밀번호 재설정 메일을 보내줌 |
| Backend | Brevo에 발송 요청 | "이 사람에게 메일 보내줘"라고 시킴 |
| Cloudflare Tunnel | 외부 주소를 내 로컬 앱으로 연결 | 내 컴퓨터 앱으로 들어오는 안전한 길 |

중요한 구분:

```text
Cloudflare Email Routing
= 받는 메일용

Brevo SMTP
= 보내는 메일용

Cloudflare Tunnel
= 웹사이트 접속용
```

즉, 이 세 개는 서로 다른 일이다.

---

## 4. Brevo와 Cloudflare DNS 연결 복습

Brevo 도메인 인증 화면에서 이런 값들이 나왔다.

```text
Brevo code
Type: TXT
Name: @
Content: brevo-code:...

DKIM 1 record
Type: CNAME
Name: brevo1._domainkey
Content: b1.travel-hunter-co-kr.dkim.brevo.com

DKIM 2 record
Type: CNAME
Name: brevo2._domainkey
Content: b2.travel-hunter-co-kr.dkim.brevo.com
```

이 값들은 어디에 넣는가?

```text
Brevo가 보여준 DNS 값
→ Cloudflare
→ travel-hunter.co.kr
→ DNS
→ Records
→ Add record
```

Cloudflare에는 대략 이렇게 들어가야 한다.

```text
TXT     @                  brevo-code:...
CNAME   brevo1._domainkey   b1.travel-hunter-co-kr.dkim.brevo.com
CNAME   brevo2._domainkey   b2.travel-hunter-co-kr.dkim.brevo.com
```

CNAME 두 개는 반드시 다음 상태여야 한다.

```text
DNS only
```

주황색 구름 `Proxied`면 안 된다.

---

## 5. Brevo sender 설정 복습

Brevo의 `Senders, Domains & Dedicated IPs` 화면에서 아래 sender가 보이면 좋다.

```text
Travel Hunter <no-reply@travel-hunter.co.kr>
Verified
```

또 아래 항목들이 정상이어야 한다.

```text
DKIM signature: travel-hunter.co.kr 정상
DMARC: configured 정상
```

이 말은 다음 뜻이다.

```text
Brevo가 no-reply@travel-hunter.co.kr 주소로 메일을 보낼 준비가 됐다.
```

기존 Gmail sender가 남아 있어도 괜찮다.

```text
Travelhunter <travelhunter.service@gmail.com>
```

하지만 나중에 비밀번호 재설정 메일 발신자로 쓸 주소는 이것이다.

```text
no-reply@travel-hunter.co.kr
```

---

## 6. 지금 당장 체크할 수 있는 것

백엔드 연결 전에도 확인할 수 있는 것이 있다.

### 6-1. Brevo 도메인 인증 상태 확인

Brevo에서 확인한다.

```text
Settings
→ Senders, domains, IPs
→ Domains
→ travel-hunter.co.kr
```

성공 상태는 보통 이런 말로 나온다.

```text
Verified
Authenticated
Configured
```

### 6-2. Brevo sender 확인

Brevo에서 확인한다.

```text
Settings
→ Senders, domains, IPs
→ Senders
```

아래가 있으면 좋다.

```text
Travel Hunter <no-reply@travel-hunter.co.kr>
Verified
```

### 6-3. Cloudflare DNS 확인

Cloudflare에서 확인한다.

```text
Cloudflare
→ travel-hunter.co.kr
→ DNS
→ Records
```

아래 3개가 있는지 확인한다.

```text
TXT     @                  brevo-code:...
CNAME   brevo1._domainkey   b1.travel-hunter-co-kr.dkim.brevo.com
CNAME   brevo2._domainkey   b2.travel-hunter-co-kr.dkim.brevo.com
```

그리고 CNAME 두 개는 `DNS only`여야 한다.

---

## 7. 백엔드는 아직 안 해도 되는가?

가능하다.

지금은 백엔드를 잠시 미뤄두고, 먼저 터널링을 준비할 수 있다.

하지만 기억해야 할 것이 있다.

```text
터널링
= 내 로컬 frontend/backend에 외부 주소로 접속하게 해주는 길

백엔드 SMTP 연결
= 비밀번호 재설정 메일을 실제로 보내게 하는 기능
```

그래서 터널링을 먼저 해도 된다.

단, 비밀번호 재설정 메일 발송은 백엔드 SMTP 연결까지 해야 완성된다.

---

## 8. Cloudflare Tunnel이란?

Cloudflare Tunnel은 쉽게 말하면 이것이다.

```text
내 컴퓨터에서 실행 중인 앱을
외부 사람이 https://travel-hunter.co.kr 같은 주소로 볼 수 있게 해주는 안전한 길
```

예를 들어 내 컴퓨터에서 frontend가 이렇게 실행 중이라고 하자.

```text
http://localhost:5173
```

Cloudflare Tunnel을 만들면 이렇게 연결할 수 있다.

```text
https://travel-hunter.co.kr
→ 내 컴퓨터의 http://localhost:5173
```

나중에 백엔드도 이렇게 연결할 수 있다.

```text
https://api.travel-hunter.co.kr
→ 내 컴퓨터의 http://localhost:8000
```

---

## 9. 터널링을 하기 전에 알아야 할 것

터널링은 이런 식으로 동작한다.

```text
사용자
→ https://travel-hunter.co.kr 접속
→ Cloudflare가 요청을 받음
→ Cloudflare Tunnel이 내 컴퓨터로 요청을 전달
→ 내 컴퓨터의 frontend가 화면을 보여줌
```

중요한 점:

```text
내 컴퓨터가 꺼져 있으면 접속이 안 된다.
frontend 서버가 꺼져 있으면 접속이 안 된다.
cloudflared가 꺼져 있으면 접속이 안 된다.
```

즉, 터널링은 배포 서버가 아니라, 내 컴퓨터를 임시 공개하는 느낌에 가깝다.

---

## 10. 터널링 전에 준비할 것

아래가 필요하다.

```text
1. Cloudflare 계정
2. travel-hunter.co.kr이 Cloudflare에 Active 상태
3. Cloudflare Zero Trust에 들어갈 수 있어야 함
4. 내 컴퓨터에서 frontend를 실행할 수 있어야 함
5. frontend 주소를 알아야 함
```

로컬 frontend 주소는 보통 이런 것 중 하나다.

```text
http://localhost:5173
http://127.0.0.1:5173
```

Vite를 사용하면 보통 `5173`이다.

---

## 11. 터널링 추천 구조

처음에는 frontend만 연결하는 것을 추천한다.

```text
travel-hunter.co.kr
→ http://localhost:5173
```

나중에 백엔드를 연결할 때는 API 주소를 따로 쓰는 것이 깔끔하다.

```text
api.travel-hunter.co.kr
→ http://localhost:8000
```

전체 구조는 이렇게 된다.

```text
사용자 브라우저
→ https://travel-hunter.co.kr
→ Cloudflare Tunnel
→ 내 컴퓨터 frontend
→ http://localhost:5173
```

나중에 백엔드까지 붙이면:

```text
사용자 브라우저
→ https://api.travel-hunter.co.kr
→ Cloudflare Tunnel
→ 내 컴퓨터 backend
→ http://localhost:8000
```

---

## 12. Cloudflare Tunnel 만들기

Cloudflare에 로그인한다.

그 다음 보통 아래 위치로 간다.

```text
Cloudflare Dashboard
→ Zero Trust
→ Networks
→ Tunnels
```

화면에 따라 이렇게 보일 수도 있다.

```text
Zero Trust
→ Access
→ Tunnels
```

또는:

```text
Zero Trust
→ Tunnels
```

찾아야 할 버튼:

```text
Create a tunnel
```

---

## 13. Tunnel 이름 정하기

터널 이름은 알아보기 쉽게 짓는다.

추천 이름:

```text
travel-hunter-local
```

뜻:

```text
Travel Hunter 로컬 개발용 터널
```

이름은 나중에 바꿔도 되지만, 처음부터 알아보기 쉽게 하는 것이 좋다.

---

## 14. cloudflared 설치하기

Cloudflare Tunnel은 내 컴퓨터에 `cloudflared`라는 프로그램을 설치해서 동작한다.

Cloudflare가 터널 생성 화면에서 운영체제별 설치 방법을 보여준다.

Windows라면 보통 다음 흐름이다.

```text
1. Windows 선택
2. Cloudflare가 보여주는 설치 명령 또는 다운로드 안내 확인
3. cloudflared 설치
4. Cloudflare가 보여주는 실행 명령 복사
5. PowerShell에서 실행
```

중요:

```text
Cloudflare가 보여주는 token 값은 비밀값이다.
GitHub에 올리면 안 된다.
다른 사람에게 보내면 안 된다.
```

Cloudflare가 보여주는 실행 명령은 보통 이런 모양이다.

```text
cloudflared tunnel run --token 긴_토큰값
```

또는 Docker를 쓰면 이런 식일 수 있다.

```text
docker run cloudflare/cloudflared:latest tunnel --no-autoupdate run --token 긴_토큰값
```

처음에는 Cloudflare 화면이 알려주는 명령을 그대로 사용하는 것이 제일 쉽다.

---

## 15. Public Hostname 추가하기

Tunnel을 만들고 connector가 연결되면, 이제 public hostname을 추가한다.

쉽게 말하면:

```text
어떤 공개 주소를
내 컴퓨터의 어떤 로컬 주소로 보낼지 정하는 단계
```

Cloudflare Tunnel 화면에서 다음 메뉴를 찾는다.

```text
Public Hostnames
→ Add a public hostname
```

처음에는 frontend만 연결한다.

입력 예시:

```text
Subdomain: 비워둠
Domain: travel-hunter.co.kr
Path: 비워둠
Type: HTTP
URL: localhost:5173
```

화면에 따라 URL 칸에 이렇게 넣어야 할 수도 있다.

```text
http://localhost:5173
```

결과:

```text
https://travel-hunter.co.kr
→ http://localhost:5173
```

---

## 16. frontend 켜기

터널만 만든다고 화면이 뜨는 것은 아니다.

내 컴퓨터에서 frontend가 켜져 있어야 한다.

예를 들어 Vite 프로젝트라면 보통 이렇게 실행한다.

```bash
npm run dev
```

frontend가 켜지면 보통 이런 주소가 나온다.

```text
http://localhost:5173
```

이 주소가 로컬 브라우저에서 먼저 열려야 한다.

먼저 확인:

```text
http://localhost:5173 접속
→ 화면이 잘 나옴
```

그 다음 확인:

```text
https://travel-hunter.co.kr 접속
→ 같은 화면이 잘 나옴
```

---

## 17. 터널링 성공 기준

아래가 되면 frontend 터널링은 성공이다.

```text
1. 내 컴퓨터에서 frontend가 켜져 있다.
2. Cloudflare Tunnel 상태가 Healthy 또는 Connected다.
3. Public hostname에 travel-hunter.co.kr이 있다.
4. https://travel-hunter.co.kr로 접속했을 때 frontend 화면이 나온다.
```

---

## 18. 자주 나는 문제와 해결 방법

### 문제 1. travel-hunter.co.kr에 접속해도 안 열린다

확인할 것:

```text
1. frontend가 켜져 있는가?
2. http://localhost:5173은 내 컴퓨터에서 열리는가?
3. cloudflared가 실행 중인가?
4. Tunnel 상태가 Healthy 또는 Connected인가?
5. Public hostname URL이 localhost:5173으로 되어 있는가?
```

### 문제 2. Tunnel은 켜져 있는데 502 오류가 난다

대부분 이런 뜻이다.

```text
Cloudflare는 내 컴퓨터로 찾아왔는데,
내 컴퓨터의 localhost:5173에 앱이 없거나 꺼져 있다.
```

확인할 것:

```text
frontend 실행 여부
포트 번호 5173이 맞는지
Public hostname의 URL이 맞는지
```

### 문제 3. DNS record가 자동으로 생겼다

정상일 수 있다.

Cloudflare Tunnel에서 public hostname을 추가하면, Cloudflare가 그 hostname을 tunnel로 보내는 DNS record를 자동으로 만들 수 있다.

예를 들면:

```text
travel-hunter.co.kr
→ 어떤-tunnel-id.cfargotunnel.com
```

이것은 터널로 보내기 위한 DNS 연결이다.

### 문제 4. 예전 웹사이트가 뜬다

확인할 것:

```text
1. Cloudflare DNS에서 travel-hunter.co.kr 레코드가 터널을 가리키는가?
2. 기존 A record나 CNAME record가 남아 충돌하지 않는가?
3. 브라우저 캐시 문제는 아닌가?
```

처음에는 시크릿 창으로 접속해보는 것도 좋다.

### 문제 5. 내 컴퓨터를 껐더니 사이트가 안 열린다

정상이다.

Cloudflare Tunnel은 내 컴퓨터에서 실행 중인 앱으로 연결하는 길이다.

```text
내 컴퓨터 꺼짐
→ frontend 꺼짐
→ cloudflared 꺼짐
→ 외부 접속 안 됨
```

계속 켜져 있어야 하는 서비스라면 나중에 VPS, 서버, 배포 환경으로 옮기는 것이 좋다.

---

## 19. 백엔드를 나중에 붙일 때

백엔드를 연결할 때는 public hostname을 하나 더 추가한다.

예시:

```text
Subdomain: api
Domain: travel-hunter.co.kr
Type: HTTP
URL: localhost:8000
```

결과:

```text
https://api.travel-hunter.co.kr
→ http://localhost:8000
```

그 다음 frontend에서 API 주소를 이쪽으로 맞추게 된다.

예:

```env
VITE_API_BASE_URL=https://api.travel-hunter.co.kr
```

프로젝트의 실제 환경변수 이름은 코드에 따라 다를 수 있다.

---

## 20. 비밀번호 재설정 메일과 터널링의 관계

나중에 비밀번호 재설정 메일을 보낼 때 중요한 값이 있다.

```env
TRAVEL_HUNTER_PUBLIC_BASE_URL=https://travel-hunter.co.kr
```

이 값은 이메일 안에 들어가는 링크의 앞부분이다.

예를 들어 위 값이 `https://travel-hunter.co.kr`이면, 메일 링크는 이런 식으로 만들어진다.

```text
https://travel-hunter.co.kr/reset-password?token=...
```

로컬 테스트라면 이렇게 쓸 수 있다.

```env
TRAVEL_HUNTER_PUBLIC_BASE_URL=http://localhost:5173
```

터널링으로 외부 테스트를 한다면 이렇게 쓰는 것이 자연스럽다.

```env
TRAVEL_HUNTER_PUBLIC_BASE_URL=https://travel-hunter.co.kr
```

---

## 21. 다음 진행 순서 추천

지금부터는 이 순서로 가면 된다.

```text
1. Cloudflare Zero Trust로 이동
2. Tunnel 생성
3. 이름을 travel-hunter-local로 지정
4. Windows용 cloudflared 설치
5. Cloudflare가 보여주는 run 명령 실행
6. Tunnel 상태가 Connected/Healthy인지 확인
7. Public hostname 추가
8. travel-hunter.co.kr → localhost:5173 연결
9. frontend 실행
10. https://travel-hunter.co.kr 접속 테스트
11. 나중에 api.travel-hunter.co.kr → localhost:8000 추가
12. 나중에 backend/.env에 Brevo SMTP 값 추가
13. 비밀번호 재설정 메일 테스트
```

---

## 22. 최종 체크리스트

터널링 전 현재 상태:

```text
[ ] Cloudflare 도메인 Active
[ ] Brevo DNS records Cloudflare에 추가
[ ] Brevo domain Verified 또는 Authenticated
[ ] Brevo sender no-reply@travel-hunter.co.kr Verified
[ ] DKIM 정상
[ ] DMARC 정상
```

터널링 진행 중:

```text
[ ] Cloudflare Zero Trust에서 Tunnel 생성
[ ] cloudflared 설치
[ ] cloudflared 실행
[ ] Tunnel Connected 또는 Healthy
[ ] Public hostname 추가
[ ] travel-hunter.co.kr → localhost:5173
[ ] frontend 실행
[ ] https://travel-hunter.co.kr 접속 성공
```

나중에 백엔드 연결:

```text
[ ] api.travel-hunter.co.kr → localhost:8000
[ ] backend/.env에 Brevo SMTP 값 입력
[ ] SMTP_PASSWORD에 Brevo 로그인 비밀번호가 아니라 SMTP key 입력
[ ] backend 재시작
[ ] /forgot-password 테스트
[ ] reset email 수신
[ ] reset link 클릭
[ ] 새 비밀번호 설정
[ ] 새 비밀번호로 로그인
```

---

## 23. 한 줄 결론

지금까지는 `도메인과 메일 발신 권한`을 준비한 것이고, 다음 터널링은 `travel-hunter.co.kr 주소로 내 로컬 frontend에 접속하는 길`을 만드는 작업이다. 터널링까지 되면 나중에 백엔드 SMTP 연결과 비밀번호 재설정 테스트를 훨씬 실제 서비스처럼 확인할 수 있다.
