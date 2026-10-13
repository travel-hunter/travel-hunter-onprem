# 로그 장기 보관 운영 절차

설계와 결정 경위: `docs/superpowers/plans/2026-09-28-pull-logs-to-local.md` (rev4~rev7) · 날짜별 배치: `docs/superpowers/plans/2026-10-08-log-daily-archive.md`

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
    2026-10\                            달 폴더
      caddy-access-2026-10-08.log         오늘 - 계속 이어 붙는다
      caddy-access-2026-10-07.p01-<해시>.log.gz   지난 날 - 다음 날 01시 넘어 압축. 늦게 온 줄은 p02 …
      backend-2026-10-07.p00-<해시>.log.gz        옛 달별 파일에서 옮긴 줄 (변환 한 번)
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

- 압축된 날도 알아서 풀어 읽는다. 변환 전 달별 파일과 섞여 있어도 함께 읽는다. 한 번에 읽는 양은 `--max-mb`(기본 64).
- 스크립트 없이 `D:\travel-hunter-logs\dev\` 를 열어도 된다(한 줄에 JSON 하나).

## 확인

```bash
docker ps --filter name=logarchive                         # 떠 있는지
docker logs --tail 5 travel-hunter-onprem-logarchive-1     # 5분마다 "dev: caddy-access +…KB, backend +…KB"
ls -la /mnt/d/travel-hunter-logs/dev /mnt/d/travel-hunter-logs/dev/$(TZ=Asia/Seoul date +%Y-%m)   # 오늘 파일이 커지는지, .state.json 시각이 최근인지
```

매달 1일에는 그 달의 첫 줄을 받는 `logarchive` 회차(보통 최대 5분)가 돌기 전까지 이번 달 폴더가 없어 `ls` 가 `No such file or directory` 를 낸다. 고장이 아니다 — 몇 분 뒤 다시 본다.

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
- 보관 폴더의 달 폴더(`YYYY-MM\`)에 손으로 `<stem>-YYYY-MM-DD.log` 를 넣지 말 것. 기록에 없는 파일은 저장 전에 멈춘 흔적으로 보고 지운다.
- 보존(`--keep-months`)은 달 폴더 단위다. 오래된 달 폴더 안의 보관 파일을 지우고, 다른 파일이 있으면 폴더는 남긴다.
- `docker compose down -v` 금지(볼륨의 단기 로그가 사라진다).
- **개발 배포가 D: 에 의존한다.** `/mnt/d` 가 없으면 `logarchive` 가 못 떠 `up --wait` 가 실패한다.
- `logarchive` 는 root 로 돈다. Caddy 가 접근 로그를 root 전용(0600)으로 만들기 때문이다. D: 는 소유자를 저장하지 않아 파일이 uid 1000·전체 권한으로 보인다. 개인 PC 라 그대로 둔다.
- `./scripts` 를 그대로 붙인다. 배포의 `git pull` 이 스크립트를 바꾸면 다음 회차부터 새 코드다.
- 같은 PC 의 다른 디스크다. PC 자체 다운·D: 고장까지는 못 막는다. 다음 단계는 다른 기계(NAS)나 S3 로 한 번 더 복사.
- 정전 직후에는 디스크 동기화를 하지 않아 상태와 보관본이 어긋나 일부 줄을 잃을 수 있다.
- AWS 로 옮기면 빼 오는 곳이 CloudWatch 로 바뀐다. 보관 형식과 `trace --dir` 은 그대로 쓴다.

## 옛 달별 파일 옮기기 (한 번, 2026-10)

날짜별 배치 이전의 달별 파일(맨 위의 `<stem>-YYYY-MM.log`, `<stem>-YYYY-MM.pNN-<해시>.log.gz`)을 `scripts/convert_log_archive.py` 로 한 번 옮긴다. 새 `pull_logs.py` 는 맨 위 옛 파일을 자르지도·압축하지도·지우지도 않는다(보존 기간 밖이어도) — 변환의 몫이다.

- 새 코드가 한 번 돈 뒤에만 된다. `YYYY-MM\` 달 폴더가 없으면 `convert` 는 거부한다(종료 코드 3).
- 각 줄은 줄 시각(KST)의 날로 간다. 시각이 없는 줄은 바로 앞 줄의 날로(그 달 첫 줄이면 1일). 결과는 `YYYY-MM\<stem>-YYYY-MM-DD.p00-<해시>.log.gz` — p00 은 변환만 쓰는 번호라 그날의 새 기록(p01~, `.log`)보다 먼저 읽힌다.
- 평문 달 파일은 `.state.json` 의 확정 크기까지만 옮긴다(그 뒤 꼬리는 새 코드가 볼륨에서 다시 받았다). 같은 달 조각과 해시가 같은 평문(압축 뒤 원본 삭제 전에 멈춘 흔적)은 건너뛴다.
- 원본은 `.legacy-monthly\` 로 옮겨 둔다. `trace --dir` 는 그 폴더를 읽지 않는다. 같은 내용은 같은 이름이라 다시 돌려도 그대로다.
- 같은 날에 다른 내용의 p00 이 이미 있거나, 옛 `.gz` 가 깨졌으면 그 달에서 멈춘다(종료 코드 3). 그 달은 아무것도 쓰지 않는다. stem 이름순으로 한 stem 의 모든 달을 끝낸 뒤 다음 stem 으로 간다(`backend` 의 달들 → `caddy-access` 의 달들, 각 stem 안에서는 달 순서). 그래서 멈춘 달보다 앞선 것(같은 stem 의 앞 달, 앞 stem 전부 — 예: `caddy-access` 에서 멈추면 `backend` 는 모두)은 이미 옮겨졌고, 그 달과 뒤의 것은 그대로다.
- `pull_logs.py` 와 같은 잠금을 잡는다. 그동안 `logarchive` 회차 하나가 `오류: 다른 실행이 진행 중이다` 로 쉬고 다음 회차에 따라잡는다. 변환이 잠금 때문에 거부되면 몇 초 뒤 다시.
- 줄 내용은 출력하지 않는다. 날마다 줄 수·바이트·sha256 앞 12자만.

**종료 코드:** `0` 모두 맞음 · `1` 끝났지만 검증표에 `DIFF` 가 있다(remove 하지 말 것) · `3` 오류(stderr 에 `오류: …`, 그 달 원본은 그대로). 인자가 틀리거나 보관 폴더가 없으면 argparse 가 `2` 로 끝낸다.

모든 명령은 개발서버에서, 보관본을 열지 않고 개수·크기·줄 수·해시만 낸다. 단계마다 사용자 승인 뒤에 돌린다.

1. **변환 전 기록 (읽기만).**
   ```bash
   cd /mnt/d/travel-hunter-logs/dev && for f in backend-20*.gz caddy-access-20*.gz; do [ -e "$f" ] || continue; gzip -t "$f" 2>/dev/null || echo "BROKEN $f"; done; echo gzip-check-done
   cd /mnt/d/travel-hunter-logs/dev && du -sh . && find . -type f | wc -l && for f in backend-20* caddy-access-20*; do [ -e "$f" ] || continue; case "$f" in *.gz) n=$(gzip -dc "$f" | wc -l);; *) n=$(wc -l < "$f");; esac; echo "$f lines=$n bytes=$(stat -c %s "$f")"; done
   cd ~/travel-hunter-onprem && scripts/trace --dir /mnt/d/travel-hunter-logs/dev --recent --since 60d --max-mb 1024 --color never | sort | uniq -d | wc -l
   ```
   - `BROKEN` 이 한 줄이라도 나오면 **멈춘다**. 깨진 옛 `.gz` 는 변환을 멈추게 한다 — 그 파일을 어떻게 할지(살릴 수 있는 만큼 풀기 / 버리기) 사용자가 정한다.
   - 마지막 숫자는 trace 출력에서 두 번 이상 나온 줄 수다(내용은 내지 않는다). 변환 전에도 0 이 아닐 수 있다(확정 크기 뒤 꼬리가 옛 파일과 날짜별 파일에 함께 있으면). 기록해 두고 3단계와 비교한다. `--max-mb 1024` 는 기본 64MB 상한이 비교를 자르지 않게 한다.
2. **크기 확인 (읽기만, 크기만).** 변환은 (stem, 달) 하나를 통째로 메모리에 올린다. 그 달의 평문과 모든 조각을 **푼** 크기의 합이 `MAX_MONTH_BYTES`(1 GiB)를 넘으면 `convert` 도 `verify` 도(그래서 `remove` 도) 그 달에서 오류(종료 코드 3)로 멈추고 그 달은 아무것도 바꾸지 않는다. `.gz` 는 `stat` 로는 모르니 풀어서 센다.
   ```bash
   cd /mnt/d/travel-hunter-logs/dev && for f in backend-20* caddy-access-20*; do [ -e "$f" ] || continue; case "$f" in *.gz) b=$(gzip -dc "$f" | wc -c);; *) b=$(stat -c %s "$f");; esac; echo "${f%%.*} $b"; done | awk '{s[$1]+=$2} END {for (k in s) printf "%s unpacked_mb=%.1f\n", k, s[k]/1048576}'
   free -m
   ```
   - 평문은 통째로 세므로 실제(확정 크기까지)보다 조금 클 수 있다.
   - 변환은 컨테이너가 아니라 호스트의 `python3` 로 돈다. 순간 메모리는 그 달 크기의 약 2~3배다 — `free -m` 의 available 이 가장 큰 달의 3배보다 작으면 멈춘다.
   - 어느 달이 수백 MB 를 넘으면 변환하지 말고 다시 판단한다. 잠금은 `LOCK_STALE_SECONDS`(3600초)보다 오래되면 지워지므로, 변환이 한 시간을 넘으면 `logarchive` 회차와 겹친다. 지금 크기면 수 초다.
3. **변환 (승인 후).** 호스트의 `python3` 로 돈다. 보관 폴더는 drvfs 라 `deploy` 로 쓸 수 있다.
   ```bash
   cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py convert --dest /mnt/d/travel-hunter-logs --label dev
   ```
   출력은 `stem 날 lines= bytes= sha= OK|DIFF` 와 달별 `합계` 행, 마지막 `검증: 모두 맞음`. 종료 코드 1·3 이면 멈추고 보고한다.
4. **변환 뒤 확인 (읽기만).**
   - 검증표의 달별 `합계 lines` = 1단계에서 그 달 파일들의 줄 수 합. 단, 평문 이번 달 파일은 확정 크기 뒤 꼬리만큼, 같은 해시의 조각과 함께 남은 지난달 평문은 통째로 적을 수 있다 — 차이가 나면 `bytes` 와 파일 이름으로 어느 쪽인지 확인해 보고한다.
   - ```bash
     cd /mnt/d/travel-hunter-logs/dev && find . -name "*.p00-*.log.gz" | wc -l && ls -la .legacy-monthly && ls backend-20* caddy-access-20* 2>/dev/null | wc -l
     cd ~/travel-hunter-onprem && scripts/trace --dir /mnt/d/travel-hunter-logs/dev --recent --since 60d --max-mb 1024 --color never | sort | uniq -d | wc -l
     ```
     p00 개수 = 검증표의 날 행 수, 맨 위 옛 파일 0개, 중복 줄 수는 **1단계 숫자 이하**. 늘었으면 멈추고 보고한다. 전체 줄 수는 비교하지 않는다 — 변환이 꼬리 중복을 지워 정상적으로도 줄 수 있다.
   - 변환이 도중에 멈추면 그 달의 줄이 다시 convert 할 때까지 trace 에 두 번 보일 수 있다. 원인을 고치고 convert 를 다시 돌린다.
5. **원본 삭제 — 보류(사용자 결정, 이번 반영에 포함하지 않음).** `.legacy-monthly\` 의 원본은 당분간 지우지 않는다. 명령은 코드에 남아 있고, 검증이 모두 맞고 맨 위에 옮기지 않은 원본이 없을 때만 지운다(아니면 종료 코드 3). 나중에 지우기로 정하면 하루 이상 지난 뒤(자정+1시간을 지나 배포일이 p01 로 닫히고, `docker logs` 에 오류가 없고, 사용자가 `trace --dir` 로 아는 문의 코드 하나를 직접 확인한 뒤) 다시 승인을 받아:
   ```bash
   cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py verify --dest /mnt/d/travel-hunter-logs --label dev | tail -1
   cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py remove --dest /mnt/d/travel-hunter-logs --label dev
   cd /mnt/d/travel-hunter-logs/dev && ls -a && du -sh .
   ```
   **`remove` 가 되돌릴 수 없는 지점이다.** `.state.json` 의 옛 키는 남는다(파일이 없으면 아무도 읽지 않는다).
   - **2027-09 전에 정한다.** 변환한 가장 오래된 달(2026-09)이 12개월 보존(`--keep-months 12`) 밖으로 나가는 2027-09 초에 보존 회차가 그 달 폴더의 날짜별 파일을 지운다. 그 뒤로는 `verify` 가 늘 `DIFF` 라 `remove` 가 영영 거부된다. 그때부터 `.legacy-monthly\` 는 사람이 손으로 지워야 한다 — 사용자 id 와 IP 앞자리가 들어 있어, 남겨 두면 12개월 원칙을 넘겨 보관하게 된다.

변환할 때 이미 `--keep-months` 밖인 달의 옛 파일이 있으면, 그 달의 p00 은 다음 보존 회차에 지워지고 verify 가 DIFF 가 돼 remove 가 거부된다. 그런 옛 파일은 변환 전에 사람이 지운다(개발서버 보관은 2026-09-28 부터라 지금은 해당 없음).

**되돌리기**

- **변환만 되돌리기(`remove` 전):** `logarchive` 를 잠깐 멈추고(`cd ~/travel-hunter-onprem && docker compose -p travel-hunter-onprem --env-file deploy/.env.dev -f compose.yaml stop logarchive` — `deploy/.env.dev` 는 상대 경로라 저장소 폴더에서 돌린다), `cd /mnt/d/travel-hunter-logs/dev && mv .legacy-monthly/* . && rmdir .legacy-monthly && find 20* -name '*.p00-*.log.gz' -delete`, 다시 `start logarchive`. p00 은 변환만 만들므로 지워도 새 기록은 남는다.
- **코드 되돌리기:** 위 변환 되돌리기를 먼저 하고, develop 에서 머지 커밋을 revert → 배포. 옛 코드는 `YYYY-MM/` 를 이름 규칙상 보지 않는다 — 새 코드가 쓴 날짜별 파일은 그대로 디스크에 남고(옛 `trace --dir` 에는 안 보임, `zcat`/`grep` 으로는 보임), 다시 배포하면 다시 보인다. 받은 위치(inode)는 그대로라 옛 코드가 이어서 받는다. 옛 코드가 다시 만드는 맨 위 이번 달 파일은 확정 크기 기록과 어긋나도 작아서 잘리지 않는다(`size > committed` 일 때만 자른다).
- **`remove` 뒤:** 달별 배치로는 돌아갈 수 없다. 데이터는 날짜별 파일에 모두 있고 새 코드의 `trace` 로 읽는다.

remove 뒤에는 convert_log_archive.py 와 그 테스트를 지우는 PR 을 올린다.

## 다른 PC 에서 받아 오기 (선택)

`logarchive` 없이도 다른 PC 에서 SSH 로 받아 올 수 있다(`docker exec` 방식):

```bash
python scripts/pull_logs.py --dev --dest D:/travel-hunter-logs
```
