# 로그 장기 보관 운영 절차

설계와 결정 경위: `docs/superpowers/plans/2026-09-28-pull-logs-to-local.md` (rev4~rev7)

## 구조

```
개발서버 PC (Windows + WSL)
 Caddy·backend 컨테이너
      │ 직접 기록
      ▼
 ① Docker 볼륨 travelhunter-logs      단기. 스트림당 20MB x 10개, 넘으면 오래된 것부터 삭제
    caddy-access.log …                  Caddy 서비스 상태 로그 (요청마다 경로·상태 코드·소요시간)
    backend.log …                       앱 로그
      │ logarchive 컨테이너가 5분마다 새 줄만 읽어 이어 붙인다 (볼륨은 읽기 전용)
      ▼
 ② D:\travel-hunter-logs\dev\         장기. 12개월 (WSL 에서 /mnt/d/travel-hunter-logs/dev)
    caddy-access-2026-09.log            이번 달 - 계속 이어 붙는다
    caddy-access-2026-08.p01-<해시>.log.gz   지난달 - 압축되어 고정. 늦게 온 줄은 p02 …
    backend-2026-09.log
    .state.json                         어디까지 받았는지 (지우지 말 것)
```

- 보관 위치는 Docker 볼륨 밖이자 WSL 밖(그 PC 의 D: 드라이브)이다. Docker·WSL 이 고장 나도 남고, Windows 탐색기로 바로 열린다.
- `logarchive` 는 옮기는 일만 한다. 로그를 컨테이너 안에 저장하지 않는다.
- 앱·Caddy 설정과 무관하다.

## 켜는 방법 (설정)

`compose.yaml` 의 `logarchive` 서비스는 profile 이라 기본으로는 뜨지 않는다. 켜는 서버의 env 파일(개발서버는 `deploy/.env.dev`, 저장소 밖)에:

```
COMPOSE_PROFILES=logarchive
LOG_ARCHIVE_DIR=/mnt/d/travel-hunter-logs
```

- `LOG_ARCHIVE_DIR` 폴더는 미리 있어야 한다. 없으면 만들지 않고 기동이 실패한다(틀린 곳에 몰래 쌓이지 않게).
- 운영·로컬은 설정하지 않는다 → 서비스가 없다.
- 설정 후 배포(Jenkins develop)하면 함께 뜬다.

## logarchive 설정별 역할

| 설정 | 역할 |
|---|---|
| `profiles: ["logarchive"]` | 켜는 스위치. env 의 `COMPOSE_PROFILES=logarchive` 가 있는 서버에서만 뜬다 |
| `LOG_ARCHIVE_LABEL` (기본 `dev`) | 보관 폴더 안의 하위 이름(`…/dev/`) |
| 볼륨 `travelhunter-logs` (읽기 전용) | 임시 창고를 읽기만 한다. 원본 로그를 바꿀 수 없다 |
| 바인드 `LOG_ARCHIVE_DIR` → `/archive` | 보관 창고. 컨테이너가 쓸 수 있는 유일한 곳. 경로가 없으면 만들지 않고 기동 실패 |
| 바인드 `./scripts` (읽기 전용) | 실행할 스크립트. 배포로 바뀌면 다음 회차부터 적용 |
| `command` + `trap 'exit 0' TERM` | 5분마다 실행. 멈추라는 신호를 받으면 그 회차를 끝낸 뒤 멈춘다(잠금이 남지 않게) |
| `stop_grace_period: 2m` | 멈출 때 회차가 끝나길 최대 2분 기다린다 |
| `network_mode: none` | 네트워크 없음(자기 자신만). 로그를 밖으로 보낼 길이 없다 |
| `cap_drop: [ALL]` | root 의 특수 권한 전부 제거. Caddy 로그는 주인(root) 권한으로 읽힌다 |
| `security_opt: no-new-privileges` | 실행 중 권한 상승 금지 |
| `read_only: true` | 컨테이너 자체 읽기 전용. 쓸 곳은 `/archive` 뿐 |
| `mem_limit: 256m` | 메모리 상한. 넘어도 이 컨테이너만 멈춘다 |
| `restart: unless-stopped` | 죽거나 재부팅하면 자동으로 다시 뜬다(사람이 멈춘 경우 제외) |

root 로 도는 이유: Caddy 가 접근 로그를 root 전용(0600)으로 만든다. 대신 위 네 가지(`network_mode`·`cap_drop`·`no-new-privileges`·`read_only`)로 "로그를 읽어 보관 폴더에 쓰는 것 말고는 아무것도 못 하는" 상태로 둔다.

## 팀원별 허용 작업

| 작업 | 개발자 (저장소) | 리뷰·머지 담당 | 서버 운영자 (`deploy`) | 그 PC 의 Windows 사용자 |
|---|---|---|---|---|
| 로그 조회 (`scripts/trace`) | 개발서버 접근이 있으면 | O | O | D: 폴더 직접 열람 |
| 설정·스크립트 변경 | PR 로만 | 리뷰 후 머지 | PR 로만 | X |
| 켜기·끄기, 보관 경로 (env) | X | X | O (사람이 직접 수정) | X |
| 멈추기·재시작 | X | X | O | X |
| 보관 로그 삭제 | X | X | 팀 합의 후 | 팀 합의 후 |
| `.state.json` 수정·삭제 | X | X | 하지 않음 | 하지 않음 |

- 이 표는 규칙이지 기술적 차단이 아니다. `deploy` 는 docker 그룹이라 서버 root 에 준한다.
- 보관본에는 사용자 ID·IP 앞자리(`/24`)·요청 경로가 있다. D: 폴더는 그 PC 에 로그인하는 누구나 읽을 수 있다 - 여럿이 쓰는 PC 면 Windows 폴더 권한을 제한한다.

## 조회

개발서버에서:

```bash
cd ~/travel-hunter-onprem
scripts/trace --dir /mnt/d/travel-hunter-logs/dev --recent --since 7d      # 최근 7일 전체
scripts/trace --dir /mnt/d/travel-hunter-logs/dev --stats --since 30d      # 30일 요약
scripts/trace --dir /mnt/d/travel-hunter-logs/dev <문의코드> --since 90d   # 요청 하나
scripts/trace --recent --since 1h                                          # 방금 일 - 볼륨(보관본은 최대 5분 늦다)
```

- 압축된 달도 알아서 풀어 읽는다. 한 번에 읽는 양은 `--max-mb`(기본 64).
- 스크립트 없이 `D:\travel-hunter-logs\dev\` 를 열어도 된다(한 줄에 JSON 하나).

## 확인

```bash
docker ps --filter name=logarchive                         # 떠 있는지
docker logs --tail 5 travel-hunter-onprem-logarchive-1     # 5분마다 "dev: caddy-access +…KB, backend +…KB"
ls -la /mnt/d/travel-hunter-logs/dev                       # 이번 달 파일이 커지는지, .state.json 시각이 최근인지
```

로그에 `오류:` 가 찍히면 볼륨이나 보관 폴더를 못 읽은 것이다. 상태를 바꾸지 않으므로 복구되면 다음 회차가 밀린 것을 이어 받는다. Dozzle 에서도 `logarchive` 로그가 보인다.

## 멈추기·되돌리기

- 잠깐 멈추기: `docker compose -p travel-hunter-onprem --env-file deploy/.env.dev -f compose.yaml stop logarchive` (잠자는 중이면 바로, 옮기는 중이면 그 회차가 끝난 뒤 멈춘다).
- 끄기: env 에서 `COMPOSE_PROFILES` 를 지우고, 남은 컨테이너를 지운다 — profile 로 꺼진 서비스는 `--remove-orphans` 로 지워지지 않는다.
  ```bash
  docker compose -p travel-hunter-onprem --env-file deploy/.env.dev -f compose.yaml --profile logarchive rm -sf logarchive
  ```
- 보관본은 멈추거나 꺼도 그대로 남는다. 삭제는 되돌릴 수 없다.

## 주의

- **`.state.json` 을 지우지 말 것.** 지우면 볼륨 전체를 다시 받아 보관본에 중복이 생긴다(보관본은 지우지 않는다).
- 보관 폴더에 손으로 `<stem>-YYYY-MM.log` 를 넣지 말 것. 기록에 없는 파일은 저장 전에 멈춘 흔적으로 보고 지운다.
- `docker compose down -v` 금지(볼륨의 단기 로그가 사라진다).
- **개발 배포가 D: 에 의존한다.** `/mnt/d` 가 없으면 `logarchive` 가 못 떠 `up --wait` 가 실패한다.
- `logarchive` 는 root 로 돈다. Caddy 가 접근 로그를 root 전용(0600)으로 만들기 때문이다. D: 는 소유자를 저장하지 않아 파일이 uid 1000·전체 권한으로 보인다. 개인 PC 라 그대로 둔다.
- `./scripts` 를 그대로 붙인다. 배포의 `git pull` 이 스크립트를 바꾸면 다음 회차부터 새 코드다.
- 같은 PC 의 다른 디스크다. PC 자체 다운·D: 고장까지는 못 막는다. 다음 단계는 다른 기계(NAS)나 S3 로 한 번 더 복사.
- 정전 직후에는 디스크 동기화를 하지 않아 상태와 보관본이 어긋나 일부 줄을 잃을 수 있다.
- AWS 로 옮기면 빼 오는 곳이 CloudWatch 로 바뀐다. 보관 형식과 `trace --dir` 은 그대로 쓴다.

## 다른 PC 에서 받아 오기 (선택)

`logarchive` 없이도 다른 PC 에서 SSH 로 받아 올 수 있다(`docker exec` 방식):

```bash
python scripts/pull_logs.py --dev --dest D:/travel-hunter-logs
```
