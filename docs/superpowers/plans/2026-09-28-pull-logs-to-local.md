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

### rev6 — 개발서버 적용 (2026-09-29)

사용자 승인(프로젝트 밖 D: 드라이브). PR #84 머지·배포(`d8cc686`) 후 SSH 로 적용.

- 실행 방식은 cron. 사용자 질문("보통 이렇게 하나")에 대한 판단: 주기 작업을 cron 으로 돌리는 것은 가장 흔한 방식이고, 스크립트가 여러 번·중단돼도 안전하게 만들어져 있어 단순한 예약 실행과 맞는다. systemd timer 는 기록이 더 잘 남지만 sudo 로 유닛을 설치해야 해 지금은 과하다.
- `docker`·`python3` 모두 `/usr/bin` — cron 기본 PATH 로 충분.
- `/mnt/d/travel-hunter-logs` 생성, 손 실행 1회차 caddy-access 62.1KB·backend 56.4KB, 2회차 0KB.
- `deploy` crontab 에 주석 1줄 + 5분 주기 1줄. 기존 항목 뒤에 붙이는 방식(없었다).
- D: 는 drvfs 라 WSL 에서 파일 권한이 `rwxrwxrwx` 로 보인다. 개인 PC 라 그대로 둔다.
- 공유: crontab 은 저장소 밖 설정이라 PR 로 들어가지 않는다. 운영 문서 `docs/deployment-cicd/log-archive-runbook.md` 를 PR 로 남긴다.

### rev7 — cron 대신 compose 컨테이너로 옮기기 (계획, 2026-09-29)

**왜:** 팀 회의 결정은 "로그를 따로 저장 공간을 만들어 관리"였다. cron 은 서버에만 있는 설정이라 팀이 보지 못하고, 서버를 새로 만들면 빠진다. 옮기는 일을 `compose.yaml` 의 작은 컨테이너로 하면 설정이 저장소에 있어 리뷰·공유되고, 배포하면 함께 뜬다.
**바뀌지 않는 것:** 보관 위치(개발서버 PC 의 D: 드라이브, 사용자가 안 A 선택), 보관 형식, `trace --dir` 조회, 앱·Caddy·볼륨.

#### 사전 확인 (읽기 전용, 2026-09-29)

| 확인 | 결과 |
|---|---|
| `--env-file` 의 `COMPOSE_PROFILES` 가 반영되나 | 로컬 Compose v5.1.1 로 재현 — 켜면 profile 서비스가 포함되고, 없으면 빠진다 |
| 배포하는 쪽 Compose | 개발서버 호스트 v5.1.4, Jenkins 컨테이너 v5.3.1 |
| Jenkins 가 compose 를 어디서 돌리나 | `agent { label 'dev' }`, `cd /home/deploy/travel-hunter-onprem` 후 `docker compose --env-file deploy/.env.dev -f compose.yaml up -d --wait`. 호스트 경로 기준이라 상대 경로 바인드(`./deploy/Caddyfile`)가 이미 동작한다. Jenkins 컨트롤러 컨테이너 안에는 그 경로가 없지만 배포는 에이전트가 한다 |
| Docker 방식 | WSL 안 Ubuntu 24.04 의 Docker Engine 29.5.2 (Docker Desktop 아님) |
| 컨테이너에 `/mnt/d` 를 붙일 수 있나 | `docker run -v /mnt/d/travel-hunter-logs:/a:ro alpine` 으로 목록·inode 조회 성공(이 확인으로 서버에 `alpine:3.20` 이미지가 받아졌다) |

#### 설계

```
compose.yaml
 └─ logarchive                       profiles: ["logarchive"]  - 기본으로는 뜨지 않는다(운영 영향 없음)
      image: python:3.12-alpine (버전 고정)
      volumes:
        travelhunter-logs:/var/log/travelhunter:ro     ← 임시 창고를 읽기 전용으로 직접
        ${LOG_ARCHIVE_DIR}:/archive                     ← 보관 창고 (개발서버: /mnt/d/travel-hunter-logs)
        ./scripts:/app/scripts:ro                       ← 배포가 git pull 하면 다음 회차부터 새 코드
      command: 5분마다 pull_logs.py --source-dir /var/log/travelhunter --label ${LOG_ARCHIVE_LABEL:-dev} --dest /archive
      restart: unless-stopped, mem_limit 64m, 자기 로그 json-file 회전
```

- **Docker 소켓을 붙이지 않는다.** 볼륨을 직접 읽으므로 `docker exec` 가 필요 없다. 소켓은 root 급 권한이라 안 쓰는 편이 안전하다.
- `pull_logs.py` 에 **`--source-dir` 모드**를 더한다: 목록은 `os.scandir` + `stat`, 읽기는 파일을 연 뒤 `os.fstat` 으로 inode 를 다시 확인하고 `seek`·`read`. 셸을 거치지 않으므로 파일 이름이 명령에 들어가지 않는다(이름 정규식은 그대로 둔다). 회전 추적·반쪽 줄·확정 크기·조각 압축·보존은 기존 코드를 그대로 쓴다 - 원격 읽기 두 함수(`remote_files`·`fetch`)만 갈아 끼우는 자리다(rev3 에서 정한 교체 지점).
- 기존 `docker exec`(+SSH) 모드는 남긴다. 다른 PC 에서 `--dev` 로 받아 오는 용도.
- **이어받기:** 컨테이너가 붙이는 볼륨은 cron 이 `docker exec` 로 읽던 것과 같은 파일시스템이라 inode 가 같다. 같은 `/archive/dev/.state.json` 을 이어 쓰므로 중복 없이 계속 쌓인다. 둘이 겹쳐 돌아도 잠금 파일이 막는다.
- 반복은 셸 루프(`while true; do …; sleep 300; done`). 한 회차가 실패해도 루프는 계속 돈다(`|| true`). 실행 기록은 컨테이너 로그(`docker logs`·Dozzle).

#### 설정

| 위치 | 값 |
|---|---|
| `.env.example` | `COMPOSE_PROFILES=`(비움), `LOG_ARCHIVE_DIR=`, `LOG_ARCHIVE_LABEL=dev` 설명 |
| 개발서버 `deploy/.env.dev` (저장소 밖) | `COMPOSE_PROFILES=logarchive`, `LOG_ARCHIVE_DIR=/mnt/d/travel-hunter-logs` |
| 운영 | 설정하지 않는다 → 서비스가 없다 |

- profile 이 켜졌는데 `LOG_ARCHIVE_DIR` 이 비면 compose 가 기동을 거부하게 한다(`${LOG_ARCHIVE_DIR:?…}`). 비어 있으면 상대 경로·빈 경로로 붙어 엉뚱한 곳에 쌓일 수 있다. 단, 이 `:?` 는 profile 이 꺼진 곳(운영·로컬)의 `compose config` 도 막을 수 있다 - 구현 때 확인하고, 막히면 서비스 안에서 비었으면 즉시 종료하는 방식으로 바꾼다.

#### 검증

1. 자동 테스트: `--source-dir` 모드를 **실제 파일**로 — 임시 폴더에서 `os.rename` 으로 회전(`backend.log` → `.1`), 목록과 읽기 사이 회전, 반쪽 줄, 파일이 잠깐 없는 경우, 셸 문자 이름 무시. 기존 테스트 유지. 변이 확인.
2. `docker compose config`: profile 켬(서비스 있음) / 끔(없음), 운영 env(`deploy/*.example`)로도 통과.
3. 로컬 실제 실행: 로컬 볼륨을 붙여 컨테이너를 띄워 두 회차 — 두 번째는 새 줄만, 컨테이너 재생성 후 이어받기.
4. 전체 `pytest`(Linux 이미지), Python 3.10·3.11.

#### 개발서버 전환 순서 (서버 쓰기 - 적용 직전에 다시 승인)

1. `deploy/.env.dev` 에 두 줄 추가(머지 전에 - 배포 때 바로 뜨도록).
2. PR 머지 → Jenkins develop 배포 → `logarchive` 가 뜬다.
3. 확인: `docker logs travel-hunter-onprem-logarchive-1` 에 회차 기록, 보관 파일 크기 증가, `trace --dir` 조회, `.state.json` 이어받기(중복 없음).
4. 확인되면 `deploy` crontab 의 두 줄 삭제. 그 전까지 겹쳐 돌아도 잠금이 막는다.
5. 되돌리기: `.env.dev` 에서 `COMPOSE_PROFILES` 를 지우고 `docker compose … up -d --remove-orphans`, crontab 두 줄을 다시 넣는다. 보관본은 그대로.

#### 문서

- 운영 문서 `docs/deployment-cicd/log-archive-runbook.md` 는 컨테이너 기준으로 쓴다(cron 기준 초안은 이 PR 에 합친다 - 따로 올리지 않는다).
- `CHECKLIST.md`: 현재 상태·검증·위험.

#### 위험

- 작은 컨테이너가 계속 떠 있다(메모리 상한 64MB).
- `LOG_ARCHIVE_DIR` 이 개발서버 PC 전용 경로다. 다른 서버에서 profile 을 켜려면 경로를 따로 정한다.
- 보관 창고가 같은 PC 에 있다는 한계(PC·D: 고장)는 그대로다.
- `./scripts` 를 바인드하므로 배포의 `git pull` 이 코드를 바꾸면 다음 회차부터 새 스크립트로 돈다. 스크립트가 깨지면 회차가 실패만 하고(루프는 계속) 보관본·상태는 그대로다.

#### rev7 계획 검토 반영 (독립 리뷰, 2026-09-29)

판정: "수정 후 구현". 반영:

| # | 지적 | 반영 |
|---|---|---|
| HIGH | `mem_limit 64m` 이면 OOM. 한 번에 최대 `--max-mb`(기본 64MB)를 읽고 줄 나누기·합치기로 사본이 더 생긴다. 달 첫날 `archive()` 는 지난달 `.log` 전체를 `read_bytes()` + `gzip.compress()` | 압축을 스트리밍으로(`gzip.open` + `copyfileobj`, 해시도 조각씩). 컨테이너는 `--max-mb 8`, `mem_limit 256m` |
| HIGH | 셸이 PID 1 이라 SIGTERM 을 무시 → `docker stop` 10초 뒤 SIGKILL 이 실행 중인 python 을 죽이면 `.lock` 이 남아 최대 1시간(`LOCK_STALE_SECONDS`) 막힌다 | `trap 'exit 0' TERM; while :; do python …; sleep 300 & wait $!; done` + `stop_grace_period: 2m`. 잠자는 중이면 즉시, 실행 중이면 끝난 뒤 멈춘다. python 은 TERM 을 받지 않는다 |
| MEDIUM | profile 로만 꺼진 서비스는 orphan 이 아니라 `--remove-orphans` 로 안 지워질 수 있다 | 되돌리기는 `docker compose … --profile logarchive rm -sf logarchive`. 로컬에서 확인 |
| MEDIUM | `${LOG_ARCHIVE_DIR:?}` 가 profile 꺼진 곳의 `config` 를 막을지 불확실 | 긴 문법 바인드 + `source: ${LOG_ARCHIVE_DIR:-/nonexistent/log-archive}` + `bind.create_host_path: false`. `config` 는 늘 통과, 경로가 틀리면 `up` 이 크게 실패, Docker 가 D: 에 root 소유 폴더를 몰래 만들지 않는다 |
| MEDIUM | 개발 배포가 D: 에 의존한다(`/mnt/d` 가 없으면 `up --wait` 실패) | 받아들이고 운영 문서 위험에 적는다. 헬스체크는 두지 않는다(`--wait` 가 첫 회차를 기다리게 된다) |
| MEDIUM | 컨테이너는 root, cron 은 `deploy` — 소유자가 섞이면 cron 복귀·`trace --dir` 가 깨질 수 있다 | `user: "${LOG_ARCHIVE_UID:-1001}:${LOG_ARCHIVE_GID:-1001}"`(개발서버 `deploy` = 1001). 볼륨 파일은 root 644 라 읽힌다 |
| LOW | `--source-dir` 세부 | `O_NOFOLLOW`·`follow_symlinks=False`·정규 파일만, `re.fullmatch`(`$` 는 끝의 `\n` 앞에서도 맞는다), inode 는 문자열, 짧은 읽기 반복, 가짜 컨테이너가 아니라 진짜 읽기 방식 전환 |
| LOW | 이어받기 | 같은 ext4 디렉터리라 `st_ino` 가 같다. cron 과 컨테이너는 같은 WSL 커널의 9p 로 같은 파일에 접근하므로 `O_EXCL` 도 같게 동작 — 겹쳐도 "잠금 있음" 실패일 뿐. 전환 순간 crontab 을 바로 지워도 된다 |
| LOW | 기타 | 이미지 태그 고정(`python:3.12-alpine3.20`). `deploy/*.example` 은 모두 `__Deprecated_` 라 운영 검증 기준이 아니다 — 운영 env 로 `config` 는 로컬에서 대체 확인 |

#### rev7 구현 결과 (2026-09-29)

- `pull_logs.py`: 읽기 방식을 `Source`(목록·읽기 두 함수)로 나눴다 — `docker_source`(기존 docker exec) / `directory_source`(볼륨 직접). `--source-dir` 를 주면 docker 를 부르지 않는다. 압축은 1MB 조각씩 해시·gzip(한 달치를 메모리에 올리지 않는다).
- **계획과 달라진 점: 컨테이너는 root 로 돈다.** 계획 검토는 "볼륨 파일이 root 644 라 1001 로 읽힌다"고 봤지만, Caddy 는 접근 로그를 **0600** 으로 만든다 — uid 1001 로는 `Permission denied`(로컬 볼륨에서 확인). Caddy 설정을 바꾸지 않고 root 로 돌린다. 걱정했던 "보관 파일이 root 소유" 문제는 개발서버 D:(drvfs, metadata 없음)가 소유자를 저장하지 않아 생기지 않는다(cron 이 만든 파일도 uid 1000·777 로 보였다).
- `COMPOSE_PROFILES=` 빈 값은 "끔"으로 동작(확인).
- 로컬 실제 실행: 첫 회차, 재생성 후 새 줄만, `stop` 1초, `rm -sf` 제거.
- 변이: 기존 27 + 새 7 모두 잡힘. 처음엔 "목록 중 사라짐" 이 안 잡혀 테스트를 더했다.
- 전체 1,171 passed / 19 skipped(Linux). Python 3.10·3.11.
- cron 기준 운영 문서 초안은 컨테이너 기준으로 다시 썼다(같은 PR).

### rev8 — logarchive 컨테이너 권한 줄이기 (계획, 2026-09-29)

**왜:** `logarchive` 는 root 로 돈다(Caddy 접근 로그가 0600). 하는 일은 "볼륨에서 읽어 보관 폴더에 쓰기" 하나뿐이다. 그 밖의 능력을 모두 뺀다 - 스크립트가 잘못되거나 바뀌어도 로그를 밖으로 보내거나 다른 곳을 건드릴 수 없게.

| 설정 | 하는 일 | 왜 괜찮나 |
|---|---|---|
| `network_mode: none` | 이 컨테이너에만 네트워크를 주지 않는다(자기 자신 localhost 만). DB·backend·인터넷 모두 불가 | 파일만 다룬다. 다른 서비스·서버 네트워크에는 영향 없음 |
| `cap_drop: [ALL]` | root 의 특수 권한(남의 파일 권한 무시, 소유자 변경, 네트워크 설정 등)을 모두 뺀다 | Caddy 로그는 **주인이 root** 라 특수 권한 없이도 주인 권한으로 읽힌다 - 확인 필요 |
| `security_opt: [no-new-privileges:true]` | 실행 중 setuid 등으로 권한을 더 얻지 못하게 잠근다 | 권한 상승이 필요한 동작이 없다 |
| `read_only: true` | 컨테이너 자체 파일시스템을 읽기 전용으로. 쓸 곳은 붙인 `/archive` 뿐 | 스크립트는 `/archive` 에만 쓴다(상태·잠금·압축 임시 파일 포함). `PYTHONDONTWRITEBYTECODE=1` 이 이미 있다 - 확인 필요 |

**로컬 확인 (적용 전):**
1. 강화한 설정으로 로컬 볼륨에 붙여 실제로 띄운다. 진짜 `.env` 를 복사하지 않는다 - 다른 서비스의 필수 변수는 가짜 값으로 채운 임시 env 로 `config`·`up --no-deps logarchive` 만.
2. 컨테이너 안에서 확인: 네트워크 인터페이스가 `lo` 하나, 바깥 접속 실패 / `CapEff` 0 / `NoNewPrivs` 1 / 루트 파일시스템 쓰기 실패.
3. 동작 확인: 0600 Caddy 로그를 읽는다, 새 줄만 붙는다, 지난달 `.log` 를 조각 `.gz` 로 압축한다(`/archive` 에 임시 파일), 잠금·상태 저장, `stop` 이 빨리 끝난다, 재생성 후 이어받는다.
4. `docker compose config`: profile 끔·켬.

**하나라도 안 되면** 그 설정만 빼고 이유를 기록한다(예: `read_only` 가 막히면 필요한 경로에 `tmpfs` 를 준다).

**PR:** #85 는 이미 푸시돼 있다. 커밋을 고쳐 강제 푸시하지 않고 새 커밋으로 더한다. 새 HEAD 를 다시 리뷰받는다. 운영 문서·CHECKLIST 에 설정별 역할과 팀원별 허용 작업표를 넣는다.

#### rev8 결과 (2026-09-29)

- 네 설정 모두 적용. 로컬 확인: 네트워크 장치 `lo` 뿐, 외부 접속 `Network unreachable`, `CapEff: 0000000000000000`, `NoNewPrivs: 1`, 루트 쓰기 `Read-only file system`, `/archive` 쓰기 가능.
- 이 상태로 0600 Caddy 로그를 읽었다(주인 권한이라 특수 권한이 필요 없다). 지난달 `.log` 를 `/archive` 안의 임시 파일로 조각 압축했다(`read_only` 에도 `tmpfs` 가 필요 없었다).
- `stop` 2초, 재생성 후 중복 없음, `--profile logarchive rm -sf` 제거, profile 끔이면 서비스 없음.
- 진짜 `.env` 를 복사하지 않고 다른 서비스 필수 변수만 가짜 값으로 채운 임시 env 로 확인했다(확인 뒤 삭제).
- 운영 문서에 설정별 역할과 팀원별 허용 작업표를 넣었다.
- PR #85 는 머지 전이라 사용자 허락으로 커밋을 합쳐 다시 올린다(`--force-with-lease`).
