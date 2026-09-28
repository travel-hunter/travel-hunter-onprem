# 서버 로그를 내 PC 로 가져와 보관

- 브랜치: `feature/log-stack`
- 선행: PR #83(볼륨 로그 `travelhunter-logs`·`scripts/trace`) — 개발서버 배포 확인(2026-09-28, `05be510`)
- 목적(사용자): Caddy 에서 보이는 서비스 상태 로그를 **서버 밖, 내 PC 파일로** 남긴다. 서버가 다운돼도 그 전까지의 로그를 볼 수 있어야 한다.

## 왜 이 구조인가

| 상황 | 서버 볼륨(#83) | 서버 일반 폴더 | **내 PC 복사본** |
|---|---|---|---|
| 재배포 | 남음 | 남음 | 남음 |
| 서버 다운 | 복구 전까지 못 봄 | 복구 전까지 못 봄 | **바로 봄** |
| 서버 디스크 고장 | 잃음 | 잃음 | **남음** |

볼륨이든 일반 폴더든 같은 디스크다. 서버 밖에 사본이 있어야 다운·고장에 견딘다.

## 확인한 사실

- 개발서버 볼륨: `/var/lib/docker/volumes/travel-hunter-onprem_travelhunter-logs/_data`, root 전용. `deploy` 계정으로는 직접 못 읽는다 → 컨테이너(`docker exec`)를 통로로 읽는다(`scripts/trace` 와 같은 방식).
- 파일: `caddy-access.log`(Caddy 회전본은 `caddy-access-<시각>-<사유>.log`, 이름 불변), `backend.log`(회전 시 `.1 → .2` 로 **이름이 밀린다**).
- 보관 한도: 스트림당 20MB × 10개. PC 가 꺼져 있어도 이 범위 안이면 다음 실행 때 따라잡는다.
- 내 PC 는 `~/.ssh/config` 의 `dev-server` 로 키 접속한다. 대용량은 D: 에 둔다(디스크 배치 규칙).

## 구조

```
[개발서버]  travelhunter-logs 볼륨 ── docker exec (읽기만) ──┐
                                                           │ SSH
[내 PC]     작업 스케줄러 (5분마다) ──► scripts/pull_logs.py ┘
                                          │
                                          ▼
            D:\travel-hunter-logs\dev\caddy-access.log   (계속 이어 붙임)
                                     \backend.log
                                     \.state.json         (어디까지 받았는지)
```

- **PC 에 컨테이너 없음.** Python 스크립트 1개 + Windows 작업 스케줄러.
- **서버 변경 없음.** 새 컨테이너·설정 없이 읽기만 한다.

### 가져오는 방식 (증분)

파일 이름은 회전 때 바뀌므로(backend) **이름이 아니라 inode 로** 추적한다. 회전은 이름만 바꾸고 inode 는 그대로다.

1. 서버에서 `stat -c '%i %s %n'` 로 파일마다 inode·크기를 받는다.
2. 오래된 것부터 차례로, 상태 파일에 있는 inode 면 **받은 위치 이후만**, 처음 보는 inode 면 처음부터 받는다.
3. 받은 바이트는 마지막 줄바꿈까지만 쓴다(쓰는 중인 반쪽 줄 제외). 위치를 그만큼 전진.
4. 서버에서 사라진 inode 는 상태에서 지운다.
5. 로컬은 스트림마다 파일 하나에 **이어 붙인다**(`caddy-access.log`, `backend.log`). 로컬 회전은 하지 않는다.

- 한 번에 받는 양 상한(기본 64MB). 첫 실행은 서버에 남은 전부(최대 스트림당 200MB)를 받는다.
- 실패하면 상태를 바꾸지 않는다 → 다음 실행이 같은 곳부터 다시 받는다. 중복·누락 없음.
- 동시 실행 방지: 잠금 파일.

### 조회

- 로컬 파일은 한 줄 한 JSON 이라 `findstr`/`Select-String`/`grep` 으로 바로 찾는다.
- `scripts/trace --dir D:\travel-hunter-logs\dev <문의코드>` — 같은 출력 형식으로 로컬 사본을 읽는다(서버 접속 불필요). 볼륨 읽기와 같은 파서를 쓴다.

### 설치 (한 번)

```powershell
schtasks /Create /TN "TravelHunter Log Pull (dev)" /SC MINUTE /MO 5 `
  /TR "python C:\dev\travel-hunter\travel-hunter-onprem\scripts\pull_logs.py --dev --dest D:\travel-hunter-logs"
```
문서에 적고, 등록은 사용자가 한다(내 PC 설정 변경).

## AWS 이전 시 — 빼 오는 위치만 바뀐다

기존 AWS 목표 구조(`2026-09-22-caddy-service-status-log.md`): 백엔드 stdout → `awslogs` → **CloudWatch Logs**(로그 그룹 보존 30일), Caddy 대신 ALB.
그때는 서버에 들어가 볼륨을 읽는 경로(`docker exec`)가 없다. 그래서 **경계를 "개발 PC 의 파일 형식"에 둔다.**

| | 온프레미스(지금) | AWS |
|---|---|---|
| 빼 오는 곳 | 볼륨 파일(`docker exec` 로 `stat`·`tail`) | CloudWatch 로그 그룹(`aws logs filter-log-events`) |
| 증분 기준 | inode + 받은 위치 | 이벤트 시각 + 마지막 eventId |
| PC 쪽 결과 | `<dest>/<환경>/backend.log` (한 줄 한 JSON) | **같은 파일, 같은 형식** |
| 조회 | `trace --dir` | **그대로** |

- 백엔드는 이미 한 줄 한 JSON 을 stdout 에 쓰고, CloudWatch 이벤트의 message 가 그 줄이다. 변환 없이 이어 붙이면 된다.
- 엣지 로그는 달라진다. ALB 접근 로그는 S3 에 공백 구분 형식으로 간다 — `caddy-access.log` 와 형식이 달라 `trace` 의 엣지 파서를 따로 둬야 한다. 이전 계획에서 다룬다.
- AWS 에서는 CloudWatch 자체가 서버 밖 저장소라 "서버 다운 시 조회" 문제가 사라진다. PC 사본은 30일을 넘는 보관·오프라인 조회용이 된다.
- 구성도(2026-09-28 사용자 제공) 기준으로 확인되는 것:
  - 환경별 VPC(Dev·Prod), 앱은 **Auto Scaling Group 의 EC2 여러 대**(2 AZ, private subnet), 앞단 Cloudflare → ALB, DB 는 RDS, 환경마다 CloudWatch.
  - 인스턴스는 교체·축소될 수 있다 → 인스턴스 디스크의 볼륨 로그는 **보관소가 될 수 없다**(#83 볼륨은 온프레미스 전용). AWS 에서 `LOG_FILE_PATH` 는 비워 stdout → CloudWatch 만 쓴다.
  - 앱이 여러 대·private subnet 이라 `ssh` + `docker exec` 로 한 대씩 읽는 방식은 쓸 수 없다. **빼 오는 곳은 환경별 CloudWatch 로그 그룹 하나**다(인스턴스별 스트림을 합쳐 읽는다). 개발 PC 에는 읽기 전용 IAM 자격(`logs:FilterLogEvents`)이 필요하다.
  - 엣지는 Caddy 대신 ALB·Cloudflare. ALB 접근 로그는 S3 로 켜야 남는다(구성도에 경로 없음 — 이전 계획에서 결정).
  - 같은 이유로 `feature/error-alerts` 의 알림 묶음(프로세스 메모리)은 인스턴스 수만큼 울린다. AWS 에서는 CloudWatch 지표 필터 + 알람으로 옮기는 편이 맞다 — 이전 계획의 확인 항목.
- **지금 하지 않는 것:** CloudWatch 소스 구현. 구현이 하나뿐인 추상화를 미리 두지 않는다. 대신 PC 파일 형식(`<dest>/<환경>/<stem>.log`, 한 줄 한 JSON, 시간순 이어 붙임)을 이 문서에 **계약으로 고정**하고, `pull_logs.py` 의 원격 읽기(`remote_files`·`fetch`)를 한곳에 모아 두어 교체 지점이 분명하게 한다.

## 보안

- SSH 키 접속만. 비밀번호·토큰을 스크립트나 작업에 넣지 않는다.
- 서버에서 부르는 명령은 고정: `docker exec <컨테이너> sh -c "stat …/ tail -c …"`. 파일 이름은 정규식으로 거른 것만(trace 와 같은 규칙).
- 로컬 사본에는 마스킹된 로그만 있다(쿼리 화이트리스트·본문 미기록). 그래도 사용자 ID·IP 대역이 있으므로 저장소 밖 `D:\travel-hunter-logs` 에 둔다.

## 한계

- PC 가 꺼져 있는 동안은 복사되지 않는다. 서버에 남아 있는 범위(스트림당 200MB) 안에서 켜지면 따라잡는다.
- 서버가 다운되면 마지막 복사(최대 5분 전)까지만 있다.
- 로컬 파일은 계속 커진다. 하루 수 MB 수준이라 당분간 문제없다. 필요하면 월 단위로 나눈다.

## 변경 파일

- `scripts/pull_logs.py`(신규), `scripts/trace.py`(`--dir`)
- `backend/tests/test_pull_logs.py`(신규), `backend/tests/test_trace_script.py`
- 운영 문서(설치·조회), `CHECKLIST.md`, 이 계획서

## 검증

- 자동 테스트(가짜 docker): 첫 실행 전체 수신, 증분(추가분만), backend 회전(이름 밀림) 후 누락·중복 없음, Caddy 회전, 반쪽 줄 보류, 실패 시 상태 불변, 사라진 inode 정리, 셸 안전 이름, 상한.
- 변이: 핵심 규칙을 되돌리면 테스트가 실패하는지.
- 실제: 로컬 스택 대상 실행 → 요청 발생 → 재실행 시 새 줄만 추가. 개발서버 대상 `--dev` 실행(읽기 전용).
- `trace --dir` 로 로컬 사본에서 문의 코드 조회.

## 기록

### rev1 — Loki + Alloy + Grafana (보류)

웹 화면 검색. 사용자: 텍스트 조회면 충분.

### rev2 — Vector 수집기 1개 (보류)

frontend·db·cloudflared 로그까지 볼륨에 모으는 안. 사용자: 목적은 **Caddy 서비스 상태 로그**이고 그건 #83 이 이미 볼륨에 쌓는다.
로컬 검증 중 거부된 명령이 일부 실행돼 테스트 컨테이너 `vector-test` 가 떴다 — 발견 즉시 제거(볼륨 포함). 서버 영향 없음.

### rev3 — 내 PC 로 증분 복사 (제안)

사용자: 서버가 다운되면 서버 안 저장소는 조회할 수 없다 → 로컬 파일에 저장하는 게 목적. "내 PC 로 가져오기" 선택.

구현 결과(2026-09-28):

- `scripts/pull_logs.py`(신규), `scripts/trace.py` 에 `--dir`.
- 함께 고친 결함: `trace` 를 키 없이 실행하면 안내 대신 `NameError` 로 죽었다(#83 에서 `build_parser()` 를 나누며 `main()` 이 없는 `parser` 를 불렀다). 개발서버에서 사용자가 실제로 겪을 수 있던 경로다.
- 변이 11개 모두 테스트가 잡는다. 처음엔 2개가 안 잡혔다 — 가짜 원격이 파일을 이미 시간순으로 줘서 정렬이 검증되지 않았고(실제 `stat *` 처럼 이름순으로 바꿈), Windows 의 `write_text` 가 `\n` 을 `\r\n` 으로 바꿔 자르는 위치가 어긋났다(바이트로 쓰게 바꿈).
- 백엔드 전체(Linux 이미지) 1,144 passed / 19 skipped(신규 19). Python 3.11 에서 두 스크립트 `--help` 실행.
- 실제: 로컬 스택 대상 첫 실행 1.7MB, 두 번째 새 줄 0.3KB 만. Caddy 가 없는 로컬에서 backend 컨테이너로 자동 전환. `trace --dir` 로 방금 요청 조회, 사본·서버 모두 해당 줄 1개(중복 없음).
- 개발서버 `--dev`(읽기 전용): 첫 실행 caddy-access 25.0KB · backend 15.7KB, 두 번째 0KB. `trace --dir --recent`·`--stats` 로 엣지·앱 줄이 시간순으로 조회됨.
- 미확인: 작업 스케줄러 등록(사용자 몫, 머지 후 메인 체크아웃 경로로).

### rev4 — 개발서버 PC 의 로컬 디스크에 장기 보관 (승인)

사용자: 보관 위치는 Windows 개발 PC 가 아니라 **개발서버 기계의 프로젝트 밖 로컬 디스크**. 구조는 "볼륨은 회전·삭제(단기), 텍스트로 빼서 오래 보관(장기)".

확인한 사실(읽기 전용, 2026-09-28):
- 개발서버는 Windows PC 위의 WSL(Ubuntu)이다. `/` 는 WSL 가상 디스크, 그 PC 의 Windows 디스크가 `/mnt/c`·`/mnt/d`(9p).
- `/mnt/d` 797GB 여유, `deploy` 로 쓰기 가능(빈 파일을 만들었다 지워 확인). systemd·cron 동작, `deploy` crontab 비어 있음. Python 3.12.

결정:
- 보관 위치 **`/mnt/d/travel-hunter-logs`**(= 그 PC 의 `D:	ravel-hunter-logs`). Docker 볼륨 밖이자 WSL 밖이라 WSL 이 고장 나도 남고, Windows 탐색기로 바로 열린다.
- 같은 `pull_logs.py` 를 **개발서버 안에서 cron 5분 주기**로 돌린다(서버 `local` 대상). 볼륨·compose·Caddy 는 바꾸지 않는다.
- 일반적인 장기 보관 관례에 맞춰 **월별 파일 + 지난달 압축 + 보존 기간**을 더한다:
  - `<폴더>/<이름>/<stem>-YYYY-MM.log` — 줄의 시각(KST) 기준으로 달을 나눈다. 시각을 못 읽은 줄은 받은 달.
  - 지난달 파일은 `.log.gz` 로 압축. 늦게 도착한 지난달 줄은 gzip 멤버로 이어 붙인다(`gzip -dc` 가 이어서 읽는다).
  - `--keep-months`(기본 12) 보다 오래된 달은 지운다.
  - 폴더 이름은 `--label`(기본은 서버 이름). 개발서버 cron 은 `--label dev`.
- `trace --dir` 는 월별·압축 파일을 달 순서로 읽고 `--since` 이전 달은 열지 않는다.

한계: 같은 PC 의 다른 디스크다. PC 자체 다운·D: 고장은 못 막는다. 다음 단계는 다른 기계(NAS)나 S3 로 한 번 더 복사(AWS 이전 시 CloudWatch → S3 가 표준 경로).

서버 적용(쓰기 — 적용 직전에 다시 승인): 머지·배포 → `mkdir /mnt/d/travel-hunter-logs` → `deploy` crontab 한 줄.

rev4 구현 결과(2026-09-28):

- `pull_logs.py`: 달별 파일(줄 시각, KST), 지난달 `.log.gz`, `--keep-months`(기본 12), `--label`. 늦게 도착한 지난달 줄은 `.log` 로 받고 `archive()` 가 압축본 뒤에 gzip 멤버로 합친다(처음엔 받을 때 바로 압축본에 붙이는 분기도 뒀으나 archive 가 같은 일을 해 지웠다).
- `trace --dir`: 달 순서로 읽고 압축본을 풀며, `--since` 이전 달은 열지 않는다.
- 변이 18개 모두 테스트가 잡는다(줄 시각 무시, UTC 로 달 나눔, 압축·보존 생략, 압축본 덮어쓰기, --since 이전 달 읽기, 압축본·평문 순서 포함).
- 백엔드 전체(Linux 이미지) 1,153 passed / 19 skipped. Python 3.11 두 스크립트 `--help`.
- 실제: 로컬 스택에서 `--label dev` 로 실행 → `backend-2026-09.log`·`caddy-access-2026-09.log` 생성, 두 번째는 새 줄만. `trace --dir --recent`·`--stats` 조회.
- 미확인: 개발서버 `/mnt/d`(9p)에서의 실행 — 서버 쓰기라 적용 때 승인 후 확인.

### rev5 — PR 전 리뷰 결함 수정 (2026-09-28)

최종 HEAD(`b920b94`) 독립 리뷰: HIGH 없음, MEDIUM 2, LOW 여럿. MEDIUM 은 둘 다 누락·중복이라 PR 전에 고친다.

| # | 결함 | 수정 |
|---|---|---|
| M1 | `stat` 과 `tail` 사이에 backend 가 또 회전하면 `backend.log.1` 이 다른 파일이 돼, 옛 inode 의 위치로 새 파일을 읽는다(리뷰어 재현: `a b c ddddd e` → `a e b ddddd e`) | 가져오는 같은 `sh -c` 안에서 파일을 fd 로 연 뒤 `/proc/$$/fd/3` 의 inode 가 목록과 같은지 확인. 다르면 이번엔 건너뛰고 다음 실행에서 받는다. 열기 실패는 오류(이전엔 `head` 의 종료 코드에 가려 `tail` 실패가 조용히 빈 결과였다) |
| M2-a | 보관 파일에 붙인 뒤 받은 위치를 저장하기 전에 멈추면 다음 실행이 같은 줄을 다시 붙인다 | 상태에 보관 파일의 **확정 크기**도 둔다. 시작할 때 확정 크기보다 긴 파일은 꼬리를 잘라 되돌린다 |
| M2-b | 지난달 압축본에 합친 뒤 원본을 지우기 전에 멈추면(드라이브가 Windows 라 백신·열린 파일로 삭제가 실패할 수 있다) 다음 실행이 다시 합친다 | 합치지 않는다. 지난달 `.log` 는 **조각** `<stem>-YYYY-MM.pNN-<해시12>.log.gz` 로 압축한다. 같은 내용은 같은 해시라 이미 있으면 원본만 지운다. 늦게 온 줄은 다음 번호 조각. 압축은 받기 **전에도** 한 번 돌려, 멈췄던 압축을 새 줄이 섞이기 전에 마무리한다 |

LOW:
- 받은 위치를 잠금을 잡은 뒤 읽는다.
- 보관·삭제 대상 이름을 `caddy-access`·`backend` 로 한정한다(다른 `foo-YYYY-MM.log` 는 건드리지 않음).
- `trace --dir`: 최근 달부터 거꾸로 `--max-mb` 만큼만 읽는다(전에는 기간 안 전부를 메모리에). 폴더가 없으면 종료 코드 3. 깨진 압축본은 경고하고 건너뛴다.
- 두 실행이 동시에 낡은 잠금을 지우는 경쟁은 둔다 — cron 5분 간격에 실행은 수 초라 겹치기 어렵다(코드에 표시).

rev5 결과:

- 테스트가 새 경쟁 하나를 드러냈다: 회전 직후 `backend.log` 가 잠깐 없다(이름 바꾸기와 새 파일 만들기 사이). 없으면 "회전됨"으로 건너뛰고(`[ -e ]`), 있는데 못 여는 것만 오류로 했다.
- 가져오기 명령을 실제 셸에서 확인: backend 이미지(dash)·`caddy:2-alpine`(busybox) 모두 바이트 범위·inode 비교·없는 파일 처리 정상.
- 변이 27개 모두 테스트가 잡는다. 처음엔 3개가 안 잡혔다 — 두 번째 컨테이너로 넘어가 우연히 맞았고(컨테이너 하나로 시험), 깨진 파일을 건너뛰게 바꾼 뒤 `--since` 시험이 경고를 안 봤고(경고 확인 추가), 조각 번호가 두 자리라 이름순으로도 맞았다(`p99`·`p100` 으로).
- 백엔드 전체(Linux 이미지) 1,163 passed / 19 skipped. Python 3.10·3.11 두 스크립트 `--help`.
- 실제: 로컬(`--label dev`)·개발서버(`--dev`, 읽기 전용) 모두 두 번째 실행은 새 줄만.
