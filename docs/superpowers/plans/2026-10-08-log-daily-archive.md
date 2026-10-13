# 로그 장기 보관을 날짜별 파일로 나누기

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (또는 subagent-driven-development) 로 Task 단위로 진행한다. 단계는 체크박스(`- [ ]`)로 추적한다.

- 브랜치: `feature/log-daily-archive` (origin/develop `4612926` 기준 작업 트리 `.superpowers/worktrees/log-daily`)
- 선행: `docs/superpowers/plans/2026-09-28-pull-logs-to-local.md` rev4~rev8 (달별 보관, `logarchive` 컨테이너, 권한 축소) — 그 문서의 불변식을 그대로 지킨다.
- 목적(사용자): 보관본을 **날짜로 정리**한다. 한 달 파일 하나가 아니라 하루 파일 하나, 달 폴더로 묶는다.

**Goal:** `scripts/pull_logs.py` 가 `<dest>/<label>/YYYY-MM/<stem>-YYYY-MM-DD.log` 로 쓰고, 닫힌 날은 다음 날 압축한다. 기존 달별 파일은 일회성 변환으로 같은 배치로 옮긴다. `scripts/trace --dir` 는 변환 전·후 어느 상태에서도 문의 코드를 찾는다.

**Architecture:** 보관 파일 이름 규칙을 `scripts/trace.py` 한곳(`ARCHIVE_NAME`·`archive_files()`·`archive_order()`)에 두고 쓰기(`pull_logs.py`)·변환(`convert_log_archive.py`)·읽기(`trace --dir`)가 같이 쓴다. 쓰기 쪽은 날짜 키만 바뀌고 가져오기(inode·위치·반쪽 줄·확정 크기·조각 압축) 코드는 그대로다. 변환은 별도 일회성 스크립트다.

**Tech Stack:** Python 3.10+ 표준 라이브러리만, pytest. 새 의존성·compose 변경 없음.

## 지금 상태 (코드에서 확인)

- `pull()` 이 `current = "YYYY-MM"` 하나로 (1) 시각 없는 줄의 달, (2) `archive()` 의 "지난달" 기준을 정한다.
- `append_by_month()` → `<label>/<stem>-YYYY-MM.log`. 확정 크기는 `.state.json` 의 `_files[파일 이름]`.
- `roll_back_uncommitted()` 는 확정 크기보다 긴 보관 `.log` 를 잘라 되돌리고, 기록 없는 `.log` 는 지운다.
- `archive()` 는 지난달 `.log` 를 `<stem>-YYYY-MM.pNN-<sha256 12자>.log.gz` 로 압축한다. **같은 내용은 같은 이름**이라 "압축본을 만들고 원본을 지우기 전에 멈춤"(rev5 M2-b) 뒤 다시 돌아도 원본만 지운다. 늦게 온 줄은 다음 번호 조각. 보존은 `--keep-months`(기본 12)보다 오래된 달 파일 삭제.
- 이름 정규식이 두 벌이다: `pull_logs.ARCHIVE_FILE`(62–65행)과 `trace.read_local_file()` 안의 패턴(233행). 이번에 하나로 합친다.
- 기준선: `tests/test_pull_logs.py` 35 + `tests/test_trace_script.py` 61 = **96 passed**.

## 결정

| # | 결정 | 이유 |
|---|---|---|
| D1 | 배치 `<label>/YYYY-MM/<stem>-YYYY-MM-DD.log`(오늘, 5분마다 이어 붙임), 닫힌 날은 `YYYY-MM/<stem>-YYYY-MM-DD.pNN-<해시12>.log.gz`. 날은 **줄 자신의 시각(KST)**, 시각이 없으면 받은 날 | 사용자 결정. 달 나누기와 같은 규칙(`line_month` → `line_day`) |
| D2 | **해시 조각 이름을 유지**한다(사용자 예시의 `backend-2026-10-07.log.gz` 대신 `backend-2026-10-07.p01-<해시>.log.gz`) | 멈춘 압축의 재실행 안전성(rev5 M2-b)이 이름의 해시에 달려 있다. 날 단위에서도 같은 창이 있고, 늦은 줄은 오히려 더 자주 온다(아래 D3). 바꾸면 "이미 압축했나"를 알아낼 다른 장치가 필요하다 — 이름 규칙의 키만 날로 바꾸는 쪽이 가장 작다 |
| D3 | 어제 파일은 **자정 뒤 1시간(`SEAL_AFTER`) 열어 둔다** | 자정 직후 회차(00:00~00:05)는 23:55~23:59 의 어제 줄을 받는다. 바로 닫으면 매일·스트림마다 p01(압축 전)+p02(그 회차의 어제 줄)가 생긴다. 한 시간 열어 두면 보통 날은 조각 하나다. 그 뒤 늦게 온 줄은 지금처럼 p02… |
| D4 | 새 쓰기 코드는 **맨 위(옛 달별 파일)를 보지 않는다** — `YYYY-MM/` 안만 자르고·압축하고·지운다 | 변환 전까지 옛 파일이 그대로 남는다(자르지도 압축하지도 않음). 되돌리기도 깨끗하다(옛 코드는 `YYYY-MM/` 를 이름 규칙상 못 본다) |
| D5 | 변환은 **별도 일회성 스크립트** `scripts/convert_log_archive.py` (`convert` / `verify` / `remove`) | 5분 루프가 도는 `pull_logs.py` 에 일회성 분기를 넣지 않는다 — 컨테이너 루프가 변환을 부를 길이 구조적으로 없다. 다 쓰고 나면 파일 두 개(스크립트·테스트)를 지우면 끝. 잠금·이름 규칙·`line_day` 는 `pull_logs` 를 읽어 그대로 쓴다 |
| D6 | 변환 결과는 `YYYY-MM/<stem>-YYYY-MM-DD.p00-<해시>.log.gz`. **p00 은 변환만 쓰는 번호** | 변환은 배포 뒤에 돈다. 그 사이 새 코드가 배포일을 이미 p01 로 닫았을 수 있다. p00 이면 그날의 새 기록(p01~, `.log`)보다 늘 먼저 읽히고, 쓰기 쪽 번호(`1 + 최대`)는 p00 다음부터 이어진다. 같은 내용 = 같은 이름이라 다시 돌려도 그대로, 같은 날에 다른 내용의 p00 이 있으면 멈춘다. **충돌 검사는 (stem, 달)마다 모든 날을 먼저 끝내고 나서 쓴다** — 중간 날에서 멈추면 앞 날의 p00 만 써지고 원본은 맨 위에 남아 trace 가 그 날들을 두 번 읽기 때문이다 |
| D7 | 변환한 원본은 **`.legacy-monthly/` 로 옮겨 둔다**(삭제는 `remove` 만) | 원본을 남기면서도 `trace --dir` 가 같은 줄을 두 번 읽지 않는다(`.legacy-monthly` 는 달 폴더 이름이 아니라 읽지 않는다). 옮기다 멈춰도 변환은 맨 위와 `.legacy-monthly/` 를 합쳐 읽으므로 같은 내용이 된다 |
| D8 | 평문 달 파일은 `.state.json` 의 **확정 크기까지만** 변환한다(기록이 없으면 통째로) | 옛 코드가 붙이고 저장 전에 멈춘 꼬리는 옛 코드라면 다음 시작 때 잘랐다. 새 코드는 맨 위를 안 보므로(D4) 그 일을 변환이 한다. 그 꼬리는 위치가 저장되지 않아 새 코드가 볼륨에서 다시 받아 날짜별 파일에 있다. 또 **같은 달 조각과 해시가 같은 평문은 건너뛴다**(옛 `archive()` 규칙) — 옛 코드가 압축 뒤 원본 삭제 전에 멈춰(D: 의 백신이 삭제를 막는 경우) 평문과 조각이 함께 남았다면 둘 다 넣으면 같은 줄이 두 번 들어가고 verify 도 통과해 remove 가 굳혀 버린다. 깨진 옛 `.gz` 는 `ConvertError` 로 멈춘다(그 달은 아무것도 쓰지 않는다) |
| D9 | 시각을 못 읽은 줄(기동 배너 등)은 변환에서 **바로 앞 줄의 날**로, 그 달 첫 줄이면 1일로 | 변환에는 "받은 날"이 없다. 앞 줄을 따라가면 순서와 이웃이 유지된다 |
| D10 | 보존은 **달 폴더 단위**: `--keep-months` 보다 오래된 `YYYY-MM/` 안의 보관 형식 파일을 지우고 폴더가 비면 지운다. 다른 파일이 있으면 폴더째 둔다(`rmtree` 쓰지 않음) | "보관 형식이 아닌 파일은 건드리지 않는다"(기존 테스트) 불변식 유지 |
| D11 | 이름 규칙을 `trace.py` 로 옮겨 하나로 | 의존 방향이 `pull_logs → trace` 다. 쓰는 쪽과 읽는 쪽이 어긋날 수 없게. 서버 파일 이름 정규식(`_name_pattern`, stat/tail/head)은 손대지 않는다 |
| D12 | CLI: `pull_logs.py`·`trace.py` 플래그 **이름·뜻 그대로**, 바꾸는 플래그 없음. `--keep-months` 는 "그보다 오래된 달 폴더 비우기"로 같은 뜻. 새 스크립트만 `convert/verify/remove --dest --label` | 사용자 요구 |

**하지 않는 것:** 정전 대비(부팅 id 잠금, 정전 시험, 정전 뒤 절차) — 사용자 결정, AWS 이전 예정. `.state.json` 의 옛 키(`backend-2026-10.log` 등)는 `remove` 뒤에도 남긴다 — 파일이 없으면 아무도 읽지 않고, 상태 파일을 쓰는 프로그램을 늘리지 않는다. 하루 안을 시간별로 더 쪼개기, 보관본 dedup.

## Global Constraints

- 기존 불변식 그대로: inode 로 추적, 같은 명령 안에서 inode 재확인, 다시 돌려도 중복 없음(확정 크기로 꼬리 되돌리기), 반쪽 줄 안 받음, 서버에서는 `stat`·`tail`·`head` 만, 서버 파일 이름은 정규식 통과분만. `remote_files`·`fetch`·`local_files`·`local_fetch`·`pull_stream`·`Lock` 은 **수정하지 않는다**.
- 압축은 1MB 조각씩(메모리 상한 256MB 컨테이너). 하루치도 통째로 올리지 않는다.
- 보관본에는 사용자 ID·IP 대역·경로가 있다. 확인 명령은 개수·크기·줄 수·해시만 낸다. `cat`/`head`/`less` 로 보관본을 열지 않는다. 변환 스크립트도 줄 내용을 출력하지 않는다.
- `compose.yaml`·`logarchive` 설정·`.env` 를 바꾸지 않는다. `.env` 류·`.localdev/` 를 읽지 않는다.
- Python 3.10 문법(같은 따옴표를 f-string 안에 다시 쓰지 않는다 — PEP 701), 새 의존성 없음.
- 작업 트리 파일은 CRLF(autocrlf)다. Edit 도구나 UTF-8 명시 도구로만 고치고, `git diff --check` 와 U+FFFD 검사를 한다(AGENTS.md Encoding).
- `CHECKLIST.md` 는 머지 준비가 됐을 때만 고친다. 커밋은 테스트 통과 + 사용자 승인 뒤.

## Review Focus

1. **자정 경계 줄** — `23:59:59.999999+09:00` 은 그날, `00:00:00+09:00` 은 다음 날, `15:00:00+00:00`(UTC)·Caddy epoch 은 KST 로 바꿔 다음 날, 월말 줄은 다른 달 폴더. → Task 2 `test_lines_go_to_the_day_of_their_own_time`·`test_month_boundary_days_go_to_their_own_month_folder`·`test_caddy_epoch_time_is_split_in_kst`.
2. **지난 날의 늦은 줄** — 자정 뒤 한 시간은 평문에 이어 붙고 한 조각으로 닫힘, 닫힌 뒤 온 줄은 p02, 압축 중 멈춘 뒤 늦은 줄이 와도 중복 없음, 변환 p00 뒤 쓰기 번호는 p01. → Task 2 `test_yesterday_stays_open_for_the_grace_hour`·`test_late_lines_for_a_compressed_day_are_kept`·`test_interrupted_compression_is_finished_without_duplicates`, Task 3 `test_the_writer_numbers_its_chunks_after_the_converted_one`.
3. **변환 다시 돌리기** — 두 번 돌려도 파일 목록 동일, 옮기다 멈춘 뒤 다시 돌려도 중복 없음, 다른 내용의 p00 이면 멈추고 그 달은 아무 날도 쓰지 않음(trace 중복 없음), 평문+같은 해시 조각이 함께 남은 지난달은 한 번만, 깨진 옛 `.gz` 면 깨끗하게 멈춤, 확정 크기 뒤 꼬리 제외, 잠금, 새 코드가 돌기 전엔 거부. → Task 3.
4. **옛·새 배치가 섞인 trace** — 달 파일이 그 달 날짜 파일보다 먼저, `--since` 는 달 파일은 달로·날짜 파일은 날로, 잘못 놓인 이름과 `.legacy-monthly/` 는 읽지 않음, 문의 코드가 어느 쪽에 있어도 찾음. → Task 1, Task 3 `test_trace_reads_converted_and_live_lines_once_in_order`.
5. **달 폴더 단위 보존** — 12개월 밖 폴더는 비우고 지움, 보관 형식이 아닌 파일이 있으면 폴더째 둠, 맨 위 옛 파일은 보존 기간 밖이어도 안 건드림(변환 몫). → Task 2 `test_month_folders_older_than_the_keep_window_are_emptied`.

---

## 파일 구조와 책임

| 파일 | 변경 |
|---|---|
| `scripts/trace.py` | `ARCHIVE_NAME`·`MONTH_DIR`·`archive_files()`·`archive_order()` 추가, `read_local_file()` 가 두 배치를 읽는다 |
| `scripts/pull_logs.py` | `ARCHIVE_FILE` 삭제, `SEAL_AFTER`, `line_month`→`line_day`, `day_files()`, `append_by_month`→`append_by_day`, `roll_back_uncommitted`·`archive`·`pull` 이 `YYYY-MM/` 만 다룬다. 모듈 설명 갱신 |
| `scripts/convert_log_archive.py` (신규, 일회성) | 옛 달별 → 날짜별 p00, 검증표, 원본 삭제 |
| `backend/tests/test_trace_script.py` | +5 |
| `backend/tests/test_pull_logs.py` | 헬퍼 2개, "장기 보관" 절 재작성(+2), 경로 4곳, 배포 순간 시험 |
| `backend/tests/test_convert_log_archive.py` (신규) | 16 |
| `docs/deployment-cicd/log-archive-runbook.md` | 구조·조회·주의·변환 절차 |
| `docs/deployment-cicd/README.md` | 운영 문서 목록의 설명 한 줄 |
| `CHECKLIST.md` | 머지 준비 때만 |

테스트 실행(모든 Task 공통, `backend/` 에서):

```bash
cd backend
PY=C:/dev/travel-hunter/travel-hunter-onprem/backend/.venv/Scripts/python.exe
$PY -m pytest -q -p no:cacheprovider tests/test_trace_script.py tests/test_pull_logs.py tests/test_convert_log_archive.py
```

---

### Task 1: 이름 규칙을 trace.py 하나로, `--dir` 가 두 배치를 읽는다

**Files:** Modify `scripts/trace.py`, `backend/tests/test_trace_script.py`.

**Interfaces (Produces):** `trace.ARCHIVE_NAME: re.Pattern` (그룹 `stem`·`period`(`YYYY-MM` 또는 `YYYY-MM-DD`)·`part`·`hash`·`gz`), `trace.MONTH_DIR: re.Pattern`, `trace.archive_files(directory: str) -> list[tuple[str, re.Match]]` (상대 경로는 `"backend-2026-10.log"` 또는 `"2026-10/backend-2026-10-08.log"` — `/` 구분), `trace.archive_order(match) -> tuple`. Consumers: Task 2, 3.

- [ ] **Step 1: 실패 테스트를 파일 끝에 더한다.**

```python


# ----------------------------------------------------------------- 날짜별 보관본(YYYY-MM/) - 2026-10-08 계획
def _bytes(ts: str, **extra) -> bytes:
    return (app_line(ts, **extra) + "\n").encode()


def test_archive_reads_old_monthly_files_and_day_folders_together(tmp_path):
    """변환 전: 옛 달별 파일과 YYYY-MM/ 날짜별 파일이 함께 있다. 달 파일이 그 달의 날짜별 파일보다 먼저다."""
    import gzip

    (tmp_path / "backend-2026-09.p01-000000000000.log.gz").write_bytes(gzip.compress(_bytes("2026-09-20T10:00:00+09:00")))
    (tmp_path / "backend-2026-10.log").write_bytes(_bytes("2026-10-08T09:00:00+09:00"))  # 배포 전에 받은 오늘 줄
    (tmp_path / "2026-10").mkdir()
    (tmp_path / "2026-10" / "backend-2026-10-08.log").write_bytes(_bytes("2026-10-08T10:00:00+09:00"))  # 배포 뒤
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert [r["ts"][:16] for r in records] == ["2026-09-20T10:00", "2026-10-08T09:00", "2026-10-08T10:00"]


def test_day_chunks_are_read_in_number_order_before_the_plain_file(tmp_path):
    import gzip

    day = tmp_path / "2026-10"
    day.mkdir()
    (day / "backend-2026-10-07.p02-000000000000.log.gz").write_bytes(gzip.compress(_bytes("2026-10-07T23:59:00+09:00")))
    (day / "backend-2026-10-07.p00-ffffffffffff.log.gz").write_bytes(gzip.compress(_bytes("2026-10-07T09:00:00+09:00")))
    (day / "backend-2026-10-07.p01-aaaaaaaaaaaa.log.gz").write_bytes(gzip.compress(_bytes("2026-10-07T12:00:00+09:00")))
    (day / "backend-2026-10-08.log").write_bytes(_bytes("2026-10-08T00:10:00+09:00"))
    records = list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024))
    assert [r["ts"][:13] for r in records] == ["2026-10-07T09", "2026-10-07T12", "2026-10-07T23", "2026-10-08T00"]


def test_archive_since_skips_older_days_but_keeps_the_overlapping_month_file(tmp_path, capsys):
    (tmp_path / "backend-2026-09.log.gz").write_bytes(b"not gzip")  # 이전 달 - 열지 않는다
    (tmp_path / "backend-2026-10.log").write_bytes(_bytes("2026-10-08T09:00:00+09:00"))  # 걸친 달 - 연다
    (tmp_path / "2026-10").mkdir()
    (tmp_path / "2026-10" / "backend-2026-10-04.p01-000000000000.log.gz").write_bytes(b"not gzip")  # 이전 날
    (tmp_path / "2026-10" / "backend-2026-10-05.log").write_bytes(_bytes("2026-10-05T09:00:00+09:00"))
    cutoff = datetime(2026, 10, 5, tzinfo=KST)
    assert len(list(trace.read_local_file("backend", str(tmp_path), 1024 * 1024, cutoff))) == 2
    assert "읽지 못해" not in capsys.readouterr().err, "--since 이전 날·달은 열지도 않는다"


def test_archive_ignores_misplaced_and_moved_aside_files(tmp_path):
    (tmp_path / "2026-10").mkdir()
    (tmp_path / "2026-10" / "backend-2026-09-30.log").write_bytes(_bytes("2026-09-30T10:00:00+09:00"))  # 폴더와 달이 다르다
    (tmp_path / "backend-2026-10-01.log").write_bytes(_bytes("2026-10-01T10:00:00+09:00"))  # 날짜별 이름이 맨 위에
    (tmp_path / ".legacy-monthly").mkdir()
    (tmp_path / ".legacy-monthly" / "backend-2026-09.log").write_bytes(_bytes("2026-09-01T10:00:00+09:00"))  # 변환 뒤 옮긴 원본
    (tmp_path / "2026-10" / "backend-2026-10-03.log").write_bytes(_bytes("2026-10-03T10:00:00+09:00"))
    assert [r["ts"][:10] for r in trace.read_local_file("backend", str(tmp_path), 1024 * 1024)] == ["2026-10-03"]


def test_dir_mode_finds_an_inquiry_code_in_either_layout(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("--dir 은 서버에 접속하지 않는다"))
    (tmp_path / "backend-2026-10.log").write_bytes(_bytes("2026-10-08T09:00:00+09:00", request_id="old-code", path="/before"))
    (tmp_path / "2026-10").mkdir()
    (tmp_path / "2026-10" / "backend-2026-10-08.log").write_bytes(
        _bytes("2026-10-08T10:00:00+09:00", request_id="new-code", path="/after"))
    for code, path in (("old-code", "/before"), ("new-code", "/after")):
        monkeypatch.setattr("sys.argv", ["trace", "--dir", str(tmp_path), code, "--since", "", "--color", "never"])
        assert trace.main() == 0
        out = capsys.readouterr().out
        assert path in out and ("/after" if code == "old-code" else "/before") not in out
```

- [ ] **Step 2: 실행.** `$PY -m pytest -q -p no:cacheprovider tests/test_trace_script.py`
  Expected: **5 failed, 61 passed** — 새 5개(날짜 폴더를 읽지 않고, `--since` 를 달로만 비교).

- [ ] **Step 3: `DEFAULT_MAX_MB = 64` 바로 아래(색 설정 주석 위)에 이름 규칙을 둔다.**

```python
DEFAULT_MAX_MB = 64
# 장기 보관본 이름 - pull_logs.py(쓰기)·convert_log_archive.py(변환)·--dir(읽기)이 함께 쓴다.
#   맨 위       <stem>-YYYY-MM[.pNN-해시].log[.gz]      옛 달별 파일(변환 전)
#   YYYY-MM/    <stem>-YYYY-MM-DD[.pNN-해시].log[.gz]   날짜별 파일
ARCHIVE_NAME = re.compile(
    rf"^(?P<stem>{re.escape(EDGE_STEM)}|{re.escape(APP_STEM)})-(?P<period>\d{{4}}-\d{{2}}(?:-\d{{2}})?)"
    r"(?:\.p(?P<part>\d+)-(?P<hash>[0-9a-f]{12}))?\.log(?P<gz>\.gz)?$"
)
MONTH_DIR = re.compile(r"\d{4}-\d{2}")
```

- [ ] **Step 4: `read_local_file()` 바로 위에 두 함수를 더하고, `read_local_file()` 의 설명과 파일 목록 부분을 바꾼다.** (`chunks` 이후 읽기·상한·경고 코드는 그대로, 루프 머리만 `for _key, name in reversed(files):`)

```python
def archive_files(directory: str) -> list[tuple[str, re.Match]]:
    """보관 폴더의 (상대 경로, 이름 일치). 맨 위는 옛 달별 이름만, YYYY-MM/ 안은 그 달의 날짜별 이름만 받는다."""
    found = []
    for name in os.listdir(directory):
        path = os.path.join(directory, name)
        if MONTH_DIR.fullmatch(name) and os.path.isdir(path):
            for inner in os.listdir(path):
                match = ARCHIVE_NAME.fullmatch(inner)
                if match and len(match["period"]) == 10 and match["period"][:7] == name:
                    found.append((f"{name}/{inner}", match))
        elif (match := ARCHIVE_NAME.fullmatch(name)) and len(match["period"]) == 7:
            found.append((name, match))
    return found


def archive_order(match: re.Match) -> tuple:
    """읽는 순서: 기간("2026-10" 이 "2026-10-01" 보다 앞) → 조각(번호순) → 번호 없는 .gz → 평문 .log."""
    return match["period"], 2 if not match["gz"] else (0 if match["part"] else 1), int(match["part"] or 0)


def read_local_file(stem: str, directory: str, max_bytes: int, cutoff: datetime | None = None):
    """scripts/pull_logs.py 가 빼 둔 보관본을 시간순으로 읽는다. 서버 접속이 필요 없다.

    이름은 archive_files() - 옛 달별 파일(변환 전)과 YYYY-MM/ 날짜별 파일을 함께 읽는다.
    --since 이전 기간(달 파일은 달, 날짜 파일은 날로 비교)은 열지 않고, 최근 파일부터 거꾸로 --max-mb 만큼만 읽는다.
    깨진 압축본은 알리고 건너뛴다. 화면 순서는 render() 가 줄 시각으로 다시 정렬한다.
    """
    if not os.path.isdir(directory):
        raise LogReadError(f"보관 폴더가 없다: {directory}")
    first_day = cutoff.astimezone(KST).strftime("%Y-%m-%d") if cutoff else ""
    files = sorted(
        (archive_order(match), name)
        for name, match in archive_files(directory)
        if match["stem"] == stem and match["period"] >= first_day[:len(match["period"])]
    )
    chunks: list[bytes] = []
    total = 0
    for _key, name in reversed(files):
```

  `os.path.join(directory, "2026-10/backend-…")` 는 Windows 에서도 열린다. 모듈 설명 25행의 `(달별, 지난달은 .gz)` 는 `(YYYY-MM/ 날짜별, 지난 날은 .gz. 변환 전 달별 파일도)` 로 바꾼다.

- [ ] **Step 5: 실행.** 같은 명령. Expected: **66 passed** (기존 61 그대로 — 달별 이름·조각 번호순·`--since`·상한·깨진 파일 시험이 새 규칙으로도 통과).

---

### Task 2: pull_logs.py 가 날짜별로 쓴다

**Files:** Modify `scripts/pull_logs.py`, `backend/tests/test_pull_logs.py`.

**Interfaces:** Consumes Task 1. Produces `pull_logs.SEAL_AFTER`, `line_day(line: bytes, fallback: str) -> str`, `day_files(folder: Path) -> list[tuple[str, re.Match]]`, `append_by_day(folder, stem, data, today, committed)`, `archive(folder: Path, sealed: str, keep_months: int, committed: dict[str, int], save) -> None` (두 번째 인자가 `"YYYY-MM"` 에서 `"YYYY-MM-DD"` 로 바뀐다). `_files` 키는 `"YYYY-MM/<이름>"`. `ARCHIVE_FILE`·`line_month`·`append_by_month` 는 없어진다(다른 사용처 없음 — `grep` 확인됨). Consumer: Task 3.

- [ ] **Step 1: 테스트 헬퍼를 날짜 기준으로 바꾼다.** (`local()` 의 기본 날은 `NOW` 의 날 — 시각 없는 줄 `"a\n"` 은 받은 날 `2026-09-28` 로 가므로 기존 기본 시험 대부분이 그대로 맞는다)

```python
def parts(dest: Path, stem: str, day: str) -> list[Path]:
    return sorted((dest / "dev" / day[:7]).glob(f"{stem}-{day}.p*.log.gz"))


def local(dest: Path, stem: str, day: str = "2026-09-28") -> str:
    """보관본 하루치(기본: NOW 의 날). 압축 조각(번호순)과 그 뒤 붙은 .log 를 순서대로 합친다."""
    text = "".join(gzip.decompress(path.read_bytes()).decode("utf-8") for path in parts(dest, stem, day))
    plain = dest / "dev" / day[:7] / f"{stem}-{day}.log"
    if plain.exists():
        text += plain.read_bytes().decode("utf-8")
    return text
```

- [ ] **Step 2: `# ---… 장기 보관(달별·압축·보존)` 절의 시험 6개(`test_lines_go_to_the_month_of_their_own_time` ~ `test_months_older_than_the_keep_window_are_deleted`)를 아래 8개로 바꾼다.**

```python
# ----------------------------------------------------------------------------- 장기 보관(날짜별·압축·보존)
def test_lines_go_to_the_day_of_their_own_time(remote, tmp_path):
    remote.write("backend.log", json_line("2026-09-27T23:59:59.999999+09:00", "/before")
                 + json_line("2026-09-28T00:00:00+09:00", "/midnight")
                 + json_line("2026-09-27T15:00:00+00:00", "/utc"))  # UTC 15시 = KST 28일 0시
    run(tmp_path)
    assert "/before" in local(tmp_path, "backend", "2026-09-27")
    assert "/midnight" not in local(tmp_path, "backend", "2026-09-27") and "/utc" not in local(tmp_path, "backend", "2026-09-27")
    assert local(tmp_path, "backend").count("\n") == 2


def test_month_boundary_days_go_to_their_own_month_folder(remote, tmp_path):
    remote.write("backend.log", json_line("2026-08-31T23:59:00+09:00", "/aug") + json_line("2026-09-01T00:01:00+09:00", "/sep"))
    run(tmp_path)
    assert "/aug" in local(tmp_path, "backend", "2026-08-31") and "/sep" in local(tmp_path, "backend", "2026-09-01")
    assert sorted(p.name for p in (tmp_path / "dev").iterdir() if p.is_dir()) == ["2026-08", "2026-09"]


def test_caddy_epoch_time_is_split_in_kst(remote, tmp_path):
    # 2026-09-27T15:30Z = 2026-09-28 00:30 KST - UTC 로 나누면 27일로 잘못 간다.
    epoch = datetime(2026, 9, 27, 15, 30, tzinfo=timezone.utc).timestamp()
    remote.write("caddy-access.log", json.dumps({"ts": epoch, "status": 200}) + "\n")
    run(tmp_path)
    assert local(tmp_path, "caddy-access", "2026-09-28") and not local(tmp_path, "caddy-access", "2026-09-27")


def test_closed_days_are_compressed_and_today_is_not(remote, tmp_path):
    remote.write("backend.log", json_line("2026-09-27T10:00:00+09:00") + json_line("2026-09-28T10:00:00+09:00"))
    run(tmp_path)
    month = tmp_path / "dev" / "2026-09"
    assert len(parts(tmp_path, "backend", "2026-09-27")) == 1 and not (month / "backend-2026-09-27.log").exists()
    assert (month / "backend-2026-09-28.log").exists() and not parts(tmp_path, "backend", "2026-09-28")


def test_yesterday_stays_open_for_the_grace_hour(remote, tmp_path):
    """자정 직후 회차는 어제 줄을 받는다. 한 시간 열어 두어 하루가 조각 하나로 닫힌다(매일 p02 가 생기지 않게)."""
    remote.write("backend.log", json_line("2026-09-27T23:58:00+09:00", "/a"))
    run(tmp_path, now=datetime(2026, 9, 28, 0, 3, tzinfo=KST))
    remote.write("backend.log", json_line("2026-09-27T23:59:30+09:00", "/b"))
    run(tmp_path, now=datetime(2026, 9, 28, 0, 8, tzinfo=KST))
    assert not parts(tmp_path, "backend", "2026-09-27"), "자정 뒤 한 시간은 평문으로 이어 붙인다"
    run(tmp_path, now=datetime(2026, 9, 28, 1, 5, tzinfo=KST))
    [packed] = parts(tmp_path, "backend", "2026-09-27")
    assert gzip.decompress(packed.read_bytes()).decode().count("\n") == 2


def test_late_lines_for_a_compressed_day_are_kept(remote, tmp_path):
    remote.write("backend.log", json_line("2026-09-27T10:00:00+09:00", "/first"))
    run(tmp_path)
    remote.write("backend.log", json_line("2026-09-27T23:58:00+09:00", "/late"))  # 닫힌 뒤 늦게 도착한 27일 줄
    run(tmp_path)
    day = local(tmp_path, "backend", "2026-09-27")
    assert day.index("/first") < day.index("/late")
    assert [p.name.split(".")[1][:3] for p in parts(tmp_path, "backend", "2026-09-27")] == ["p01", "p02"]
    assert not (tmp_path / "dev" / "2026-09" / "backend-2026-09-27.log").exists()


def test_month_rollover_compresses_the_last_day_after_the_grace_hour(remote, tmp_path):
    remote.write("backend.log", json_line("2026-09-30T23:00:00+09:00"))
    run(tmp_path, now=datetime(2026, 9, 30, 23, 5, tzinfo=KST))
    assert (tmp_path / "dev" / "2026-09" / "backend-2026-09-30.log").exists()
    run(tmp_path, now=datetime(2026, 10, 1, 1, 5, tzinfo=KST))
    assert len(parts(tmp_path, "backend", "2026-09-30")) == 1
    assert not (tmp_path / "dev" / "2026-09" / "backend-2026-09-30.log").exists()


def test_month_folders_older_than_the_keep_window_are_emptied(remote, tmp_path):
    folder = tmp_path / "dev"
    for month in ("2025-08", "2025-09", "2025-10"):
        (folder / month).mkdir(parents=True)
        (folder / month / f"backend-{month}-01.p01-000000000000.log.gz").write_bytes(gzip.compress(b"old\n"))
    (folder / "2025-09" / "notes.txt").write_text("keep me", "utf-8")
    (folder / "backend-2025-08.log.gz").write_bytes(gzip.compress(b"legacy\n"))  # 옛 달별 파일은 변환 스크립트의 몫
    run(tmp_path, keep_months=12)  # 2026-09 기준 12개월 = 2025-10 ~ 2026-09
    assert not (folder / "2025-08").exists(), "빈 달 폴더는 지운다"
    assert [p.name for p in (folder / "2025-09").iterdir()] == ["notes.txt"], "보관 형식이 아닌 파일과 그 폴더는 남긴다"
    assert (folder / "2025-10" / "backend-2025-10-01.p01-000000000000.log.gz").exists()
    assert (folder / "backend-2025-08.log.gz").exists(), "맨 위의 옛 파일은 건드리지 않는다"
```

- [ ] **Step 3: 경로만 바뀌는 시험 4곳과 배포 순간 시험.**

  `test_label_names_the_archive_folder`:
  ```python
      assert (tmp_path / "dev" / "2026-09" / "caddy-access-2026-09-28.log").exists()
  ```
  `test_append_without_saved_state_is_rolled_back`:
  ```python
      with open(tmp_path / "dev" / "2026-09" / "caddy-access-2026-09-28.log", "ab") as handle:
  ```
  `test_an_untracked_archive_file_from_a_crash_is_removed` 의 마지막 세 줄:
  ```python
      stray = tmp_path / "dev" / "2026-09" / "backend-2026-09-28.log"
      stray.write_bytes(b"never saved\n")  # 만들고 저장 전에 멈췄다
      run(tmp_path)
      assert not stray.exists()
  ```
  `test_interrupted_compression_is_finished_without_duplicates` 본문 전체:
  ```python
      """압축본은 만들었는데 원본을 못 지우고 멈췄다. 다음 실행은 같은 해시를 찾고 원본만 지운다."""
      month = tmp_path / "dev" / "2026-09"
      remote.write("backend.log", json_line("2026-09-27T10:00:00+09:00", "/day"))
      run(tmp_path)
      [packed] = parts(tmp_path, "backend", "2026-09-27")
      restored = gzip.decompress(packed.read_bytes())
      (month / "backend-2026-09-27.log").write_bytes(restored)  # 원본이 남아 있는 상태로 되돌린다
      state_data = state(tmp_path)
      state_data["_files"]["2026-09/backend-2026-09-27.log"] = len(restored)
      (tmp_path / "dev" / ".state.json").write_text(json.dumps(state_data), "utf-8")
      # 그 사이 27일 줄이 늦게 도착한다. 압축을 먼저 마무리하지 않으면 원본+새 줄이 새 조각이 돼 /day 가 두 번 남는다.
      remote.write("backend.log", json_line("2026-09-27T23:59:00+09:00", "/late"))
      run(tmp_path)
      day = local(tmp_path, "backend", "2026-09-27")
      assert day.count("/day") == 1 and day.count("/late") == 1
  ```
  `test_directory_source_state_continues_from_docker_mode_inodes` 전체(배포 순간 — D4·D8 고정):
  ```python
  def test_directory_source_state_continues_from_docker_mode_inodes(volume, tmp_path):
      """배포 순간: 옛 달별 파일과 상태가 있다. 받은 위치(inode)는 이어받고, 옛 파일은 자르지도 압축하지도 않는다."""
      append(volume / "caddy-access.log", "old\n")
      inode = str(os.stat(volume / "caddy-access.log").st_ino)
      folder = tmp_path / "dev"
      folder.mkdir()
      (folder / "caddy-access-2026-09.log").write_bytes(b"old\nunsaved\n")  # 확정은 4바이트 - 뒤는 저장 전에 멈춘 꼬리
      (folder / "backend-2026-08.log").write_bytes(b"august\n")  # 지난달인데 아직 평문 - 옛 코드라면 압축했다
      (folder / ".state.json").write_text(json.dumps({"_files": {"caddy-access-2026-09.log": 4, "backend-2026-08.log": 7},
                                                       "caddy-access": {inode: 4}}), "utf-8")
      append(volume / "caddy-access.log", "new\n")
      run_dir(volume, tmp_path)
      assert local(tmp_path, "caddy-access") == "new\n", "받은 위치를 이어받아 old 를 다시 받지 않는다"
      assert (folder / "caddy-access-2026-09.log").read_bytes() == b"old\nunsaved\n", "꼬리는 변환이 확정 크기로 자른다"
      assert (folder / "backend-2026-08.log").read_bytes() == b"august\n" and not list(folder.glob("backend-2026-08.p*"))
      assert state(tmp_path)["_files"]["caddy-access-2026-09.log"] == 4, "변환이 읽을 확정 크기를 남긴다"
  ```

- [ ] **Step 4: 실행.** `$PY -m pytest -q -p no:cacheprovider tests/test_pull_logs.py`
  Expected: **29 failed, 8 passed** (헬퍼가 `YYYY-MM/` 를 읽는데 아직 맨 위에 쓴다).

- [ ] **Step 5: 구현 — 머리.**

  모듈 설명 11–12행:
  ```
  결과: <dest>/<label>/2026-10/caddy-access-2026-10-08.log, backend-2026-10-08.log  (오늘, 계속 이어 붙인다)
        지난 날은 조각으로 압축: 2026-10/backend-2026-10-07.p01-<해시>.log.gz (늦게 온 줄은 p02 …)
        옛 달별 파일(backend-2026-09.p01-<해시>.log.gz 등)은 건드리지 않는다 - scripts/convert_log_archive.py 가 한 번 옮긴다.
  ```
  20–21행:
  ```
  - 줄의 시각(KST)으로 날을 나눈다. 지난 날은 자정 뒤 한 시간(SEAL_AFTER)이 지나면 내용 해시 이름의 조각으로 압축한다
    (같은 내용이면 같은 이름이라 압축 중에 멈췄다 다시 해도 중복이 없다). --keep-months 보다 오래된 달 폴더는 비운다.
  ```
  import: `from datetime import datetime` 를 아래 두 줄로(`collections.abc` 다음, 알파벳순):
  ```python
  from contextlib import suppress
  from datetime import datetime, timedelta
  ```
  `ARCHIVE_FILE = re.compile(…)` 네 줄을 지우고 그 자리에:
  ```python
  # 어제 파일은 자정 뒤 이만큼 열어 둔다. 자정 직후 회차가 받는 어제 줄까지 한 조각에 들어가 매일 p02 가 생기지 않는다.
  SEAL_AFTER = timedelta(hours=1)
  ```

- [ ] **Step 6: 구현 — `line_month` 부터 `archive` 끝까지(`class Source` 앞)를 통째로 바꾼다.**

```python
def line_day(line: bytes, fallback: str) -> str:
    """줄의 시각(KST)으로 날(YYYY-MM-DD)을 정한다. 못 읽으면 fallback."""
    record = trace.parse(line.decode("utf-8", "replace"))
    when = trace.record_time(record) if record else None
    if when is None:
        return fallback
    if when.tzinfo is None:
        when = when.replace(tzinfo=trace.KST)
    return when.astimezone(trace.KST).strftime("%Y-%m-%d")


def day_files(folder: Path) -> list[tuple[str, re.Match]]:
    """YYYY-MM/ 안의 날짜별 보관 파일만 (상대 경로, 이름 일치). 맨 위의 옛 달별 파일은 보지 않는다 - 변환 스크립트의 몫이다."""
    return [(key, match) for key, match in trace.archive_files(str(folder)) if "/" in key]


def append_by_day(folder: Path, stem: str, data: bytes, today: str, committed: dict[str, int]) -> None:
    """온전한 줄들을 YYYY-MM/<stem>-YYYY-MM-DD.log 에 이어 붙이고, 붙인 뒤의 크기를 committed 에 적는다(저장은 호출자가)."""
    groups: dict[str, list[bytes]] = {}
    for line in re.findall(rb"[^\n]*\n", data):  # 줄바꿈으로만 나눈다 - data 는 온전한 줄만 담겨 온다
        groups.setdefault(line_day(line, today), []).append(line)
    for day, lines in groups.items():
        key = f"{day[:7]}/{stem}-{day}.log"
        path = folder / key
        path.parent.mkdir(exist_ok=True)
        with open(path, "ab") as handle:
            handle.write(b"".join(lines))
        committed[key] = path.stat().st_size


def roll_back_uncommitted(folder: Path, committed: dict[str, int]) -> None:
    """저장 전에 멈춘 실행이 붙인 꼬리를 잘라 되돌린다. 기록에 없는 보관 .log 는 통째로 미확정이다."""
    for key, match in day_files(folder):
        if match["gz"]:
            continue
        path = folder / key
        size = committed.get(key, 0)
        if path.stat().st_size > size:
            with open(path, "r+b") as handle:
                handle.truncate(size)
        if size == 0:
            path.unlink()
            committed.pop(key, None)


def archive(folder: Path, sealed: str, keep_months: int, committed: dict[str, int], save) -> None:
    """닫힌 날(sealed 이전)의 .log 는 조각 .gz 로, 보존 기간이 지난 달 폴더는 비운다."""
    year, month = map(int, sealed[:7].split("-"))
    total = year * 12 + month - 1 - keep_months  # 이 달과 그 이전은 지운다
    newest_dropped = f"{total // 12:04d}-{total % 12 + 1:02d}"
    files = sorted(day_files(folder), key=lambda item: item[0])
    keys = [key for key, _ in files]
    for key, match in files:
        path = folder / key
        month_dir = key.split("/")[0]
        if month_dir <= newest_dropped:
            path.unlink()
            if committed.pop(key, None) is not None:  # .gz 는 확정 크기 기록이 없다 - 바뀐 게 있을 때만 저장
                save()
        elif match["period"] < sealed and not match["gz"]:
            # 하루치도 메모리에 올리지 않는다 - 컨테이너 메모리 상한 안에서 돈다(조각씩 해시·압축).
            hasher = hashlib.sha256()
            with open(path, "rb") as source:
                for block in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(block)
            digest = hasher.hexdigest()[:12]
            prefix = f"{month_dir}/{match['stem']}-{match['period']}.p"
            existing = [k for k in keys if k.startswith(prefix)]
            if not any(k.endswith(f"-{digest}.log.gz") for k in existing):
                number = 1 + max((int(trace.ARCHIVE_NAME.fullmatch(k.split("/")[1])["part"]) for k in existing), default=0)
                target = folder / f"{prefix}{number:02d}-{digest}.log.gz"
                temp = target.with_name(target.name + ".tmp")
                with open(path, "rb") as source, gzip.open(temp, "wb") as packed:
                    shutil.copyfileobj(source, packed, 1024 * 1024)
                temp.replace(target)
                keys.append(f"{prefix}{number:02d}-{digest}.log.gz")
            path.unlink()  # 여기서 멈춰도 다음 실행이 같은 해시를 찾고 지우기만 한다
            committed.pop(key, None)
            save()
    for month_dir in {key.split("/")[0] for key in keys}:
        if month_dir <= newest_dropped:
            with suppress(OSError):  # 보관 형식이 아닌 파일이 남았으면 폴더째 둔다
                (folder / month_dir).rmdir()
```

  보존 기준 달은 `sealed` 의 달이다. 달 첫날 0~1시에는 한 달을 한 시간 더 둔다 — 무해하다.

- [ ] **Step 7: 구현 — `pull()` 네 곳.**

  ```python
      moment = (now or datetime.now(trace.KST)).astimezone(trace.KST)
      today = moment.strftime("%Y-%m-%d")
      sealed = (moment - SEAL_AFTER).strftime("%Y-%m-%d")  # 이 날 이전은 닫혔다 - 압축한다
  ```
  (`current = …` 한 줄 대신)
  ```python
              state[FILES_KEY] = {key: (folder / key).stat().st_size for key, m in day_files(folder) if not m["gz"]}
  ```
  (`_files` 가 없을 때 채우는 두 줄 대신 — 옛 키는 상태에 이미 있으면 그대로 남는다. 변환이 쓴다)
  두 `archive(folder, current, …)` 호출 → `archive(folder, sealed, keep_months, committed, save)`(주석 그대로),
  `append_by_month(folder, stem, data, current, committed)` → `append_by_day(folder, stem, data, today, committed)`.

- [ ] **Step 8: 실행.** `$PY -m pytest -q -p no:cacheprovider tests/test_pull_logs.py tests/test_trace_script.py`
  Expected: **103 passed** (37 + 66).

---

### Task 3: 일회성 변환 스크립트

**Files:** Create `scripts/convert_log_archive.py`, `backend/tests/test_convert_log_archive.py`.

**Interfaces:** Consumes `pull_logs.Lock`·`PullError`·`FILES_KEY`·`line_day`·`archive`, `trace.ARCHIVE_NAME`·`MONTH_DIR`·`archive_order`·`read_local_file`. Produces `convert(folder: Path) -> None`, `verify(folder: Path) -> tuple[list[str], bool]`, `remove(folder: Path) -> int`, `ConvertError`, `LEGACY_DIR = ".legacy-monthly"`, CLI `convert|verify|remove --dest --label`(종료 코드 0 맞음 / 1 다름 / 3 오류).

- [ ] **Step 1: 실패 테스트 `backend/tests/test_convert_log_archive.py`.**

```python
"""scripts/convert_log_archive.py — 옛 달별 보관본을 날짜별 배치로 한 번 옮긴다.

계획: docs/superpowers/plans/2026-10-08-log-daily-archive.md
"""

from __future__ import annotations

import gzip
import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "convert_log_archive.py"


def _load():
    spec = importlib.util.spec_from_file_location("convert_log_archive_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


convert = _load()
pull_logs = convert.pull_logs
trace = convert.trace


def line(ts: str, path: str, rid: str = "r1") -> bytes:
    return (json.dumps({"ts": ts, "kind": "access", "request_id": rid, "method": "GET", "path": path,
                        "status": 200, "duration_ms": 1}) + "\n").encode()


def legacy_archive(tmp_path: Path) -> Path:
    """배포 직후의 보관 폴더: 9월은 조각 둘(늦은 줄이 p02), 10월은 평문(확정 크기 뒤에 꼬리), 새 코드가 만든 오늘 파일."""
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "backend-2026-09.p01-aaaaaaaaaaaa.log.gz").write_bytes(
        gzip.compress(line("2026-09-28T10:00:00+09:00", "/sep28") + line("2026-09-30T23:58:00+09:00", "/sep30a")))
    (folder / "backend-2026-09.p02-bbbbbbbbbbbb.log.gz").write_bytes(gzip.compress(line("2026-09-30T23:59:00+09:00", "/sep30b")))
    october = (line("2026-10-01T09:00:00+09:00", "/oct1")
               + line("2026-10-08T09:00:00+09:00", "/oct8-before", "old-code") + b"uvicorn banner\n")
    (folder / "backend-2026-10.log").write_bytes(october + line("2026-10-08T09:01:00+09:00", "/unsaved-tail"))
    (folder / ".state.json").write_text(json.dumps({"_files": {"backend-2026-10.log": len(october)}}), "utf-8")
    (folder / "2026-10").mkdir()
    (folder / "2026-10" / "backend-2026-10-08.log").write_bytes(line("2026-10-08T10:00:00+09:00", "/oct8-after", "new-code"))
    (folder / "notes.txt").write_text("mine", "utf-8")
    return folder


def chunk(folder: Path, day: str) -> str:
    [path] = (folder / day[:7]).glob(f"backend-{day}.p00-*.log.gz")
    return gzip.decompress(path.read_bytes()).decode()


def trace_paths(folder: Path) -> list[str]:
    return [r["path"] for r in trace.read_local_file("backend", str(folder), 1024 * 1024)]


ALL = ["/sep28", "/sep30a", "/sep30b", "/oct1", "/oct8-before", "/oct8-after"]


def tree(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*"))


def test_monthly_files_become_day_chunks_and_move_aside(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert "/sep28" in chunk(folder, "2026-09-28")
    sep30 = chunk(folder, "2026-09-30")
    assert sep30.index("/sep30a") < sep30.index("/sep30b"), "조각 번호순 - 늦은 줄이 뒤에"
    oct8 = chunk(folder, "2026-10-08")
    assert "uvicorn banner" in oct8, "시각 없는 줄은 앞 줄의 날로 (그 달 1일이 아니라)"
    assert "/oct8-before" in oct8 and "/unsaved-tail" not in oct8, "확정 크기 뒤 꼬리는 넣지 않는다"
    assert sorted(p.name for p in (folder / ".legacy-monthly").iterdir()) == [
        "backend-2026-09.p01-aaaaaaaaaaaa.log.gz", "backend-2026-09.p02-bbbbbbbbbbbb.log.gz", "backend-2026-10.log"]
    assert not list(folder.glob("backend-*")) and (folder / "notes.txt").exists()


def test_trace_reads_converted_and_live_lines_once_in_order(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert trace_paths(folder) == ALL


def test_rerunning_the_conversion_changes_nothing(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    before = tree(folder)
    convert.convert(folder)
    assert tree(folder) == before and convert.verify(folder)[1]


def test_a_conversion_stopped_before_moving_finishes_without_duplicates(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    legacy = folder / ".legacy-monthly"
    for name in ("backend-2026-09.p02-bbbbbbbbbbbb.log.gz", "backend-2026-10.log"):
        (legacy / name).replace(folder / name)  # 조각은 썼고 원본 일부를 옮기기 전에 멈춘 상태
    convert.convert(folder)
    assert trace_paths(folder) == ALL and convert.verify(folder)[1]


def test_a_different_p00_for_the_same_day_stops_the_conversion(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "2026-10" / "backend-2026-10-08.p00-000000000000.log.gz").write_bytes(gzip.compress(b"other\n"))
    with pytest.raises(convert.ConvertError, match="다른 내용"):
        convert.convert(folder)
    assert (folder / "backend-2026-10.log").exists(), "멈춘 달의 원본은 옮기지 않는다"


def test_a_stopped_month_writes_no_day_so_trace_has_no_duplicates(tmp_path):
    """10-08 에서 멈추면 10-01 의 p00 도 쓰지 않는다. 원본이 맨 위에 남아 있으니 쓴 날은 trace 에 두 번 보인다."""
    folder = legacy_archive(tmp_path)
    (folder / "2026-10" / "backend-2026-10-08.p00-000000000000.log.gz").write_bytes(gzip.compress(b"other\n"))
    with pytest.raises(convert.ConvertError):
        convert.convert(folder)
    assert not list((folder / "2026-10").glob("backend-2026-10-01.*"))
    paths = trace_paths(folder)
    assert "/oct1" in paths and len(paths) == len(set(paths))


def test_a_past_month_left_both_plain_and_compressed_is_converted_once(tmp_path):
    folder = legacy_archive(tmp_path)
    august = line("2026-08-31T10:00:00+09:00", "/aug")
    digest = hashlib.sha256(august).hexdigest()[:12]
    (folder / f"backend-2026-08.p01-{digest}.log.gz").write_bytes(gzip.compress(august))
    (folder / "backend-2026-08.log").write_bytes(august)  # 옛 archive() 가 압축 뒤 원본 삭제 전에 멈춘 흔적
    convert.convert(folder)
    assert chunk(folder, "2026-08-31").count("/aug") == 1
    assert convert.verify(folder)[1] and not list(folder.glob("backend-*"))
    assert trace_paths(folder) == ["/aug"] + ALL
    assert convert.remove(folder) == 5


def test_a_broken_old_chunk_stops_the_conversion_cleanly(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "backend-2026-09.p03-cccccccccccc.log.gz").write_bytes(b"not gzip")
    with pytest.raises(convert.ConvertError, match="풀지 못했다"):
        convert.convert(folder)
    assert not (folder / "2026-09").exists() and (folder / "backend-2026-09.p01-aaaaaaaaaaaa.log.gz").exists()


def test_conversion_waits_for_the_new_writer(tmp_path):
    folder = legacy_archive(tmp_path)
    shutil.rmtree(folder / "2026-10")
    with pytest.raises(convert.ConvertError, match="YYYY-MM"):
        convert.convert(folder)


def test_conversion_takes_the_archive_lock(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / ".lock").touch()
    with pytest.raises(pull_logs.PullError, match="잠금"):
        convert.convert(folder)
    assert not (folder / ".legacy-monthly").exists()


def test_verify_flags_a_damaged_chunk_and_remove_refuses(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    [damaged] = (folder / "2026-09").glob("backend-2026-09-28.p00-*.log.gz")
    damaged.write_bytes(gzip.compress(b"damaged\n"))
    rows, ok = convert.verify(folder)
    assert not ok and any("2026-09-28" in row and row.endswith("DIFF") for row in rows)
    with pytest.raises(convert.ConvertError):
        convert.remove(folder)
    assert len(list((folder / ".legacy-monthly").iterdir())) == 3


def test_verify_catches_bytes_that_are_not_whole_lines(tmp_path):
    folder = legacy_archive(tmp_path)
    (folder / "backend-2026-09.p03-cccccccccccc.log.gz").write_bytes(gzip.compress(b"no newline at the end"))
    convert.convert(folder)
    rows, ok = convert.verify(folder)
    assert not ok and any("2026-09 합계" in row and row.endswith("DIFF") for row in rows)


def test_remove_refuses_while_originals_are_unconverted(tmp_path):
    folder = legacy_archive(tmp_path)
    with pytest.raises(convert.ConvertError):
        convert.remove(folder)
    assert (folder / "backend-2026-10.log").exists()


def test_remove_deletes_only_the_verified_originals(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    assert convert.remove(folder) == 3
    assert not (folder / ".legacy-monthly").exists()
    assert (folder / "notes.txt").exists() and (folder / ".state.json").exists()
    assert trace_paths(folder) == ALL


def test_the_writer_numbers_its_chunks_after_the_converted_one(tmp_path):
    folder = legacy_archive(tmp_path)
    convert.convert(folder)
    live = "2026-10/backend-2026-10-08.log"
    committed = {live: (folder / live).stat().st_size}
    pull_logs.archive(folder, "2026-10-09", 12, committed, lambda: None)  # 10-08 이 닫혔다
    parts = sorted(trace.ARCHIVE_NAME.fullmatch(p.name)["part"] for p in (folder / "2026-10").glob("backend-2026-10-08.*"))
    assert parts == ["00", "01"]
    assert trace_paths(folder) == ALL


def test_cli_prints_counts_not_log_content(tmp_path, monkeypatch, capsys):
    legacy_archive(tmp_path)
    monkeypatch.setattr("sys.argv", ["convert_log_archive.py", "convert", "--dest", str(tmp_path), "--label", "dev"])
    assert convert.main() == 0
    out = capsys.readouterr().out
    assert "2026-10-08" in out and "검증: 모두 맞음" in out
    assert "/oct8" not in out and "old-code" not in out and "banner" not in out
```

- [ ] **Step 2: 실행.** `$PY -m pytest -q -p no:cacheprovider tests/test_convert_log_archive.py`
  Expected: **1 error** — 수집 중 `FileNotFoundError: …scripts\convert_log_archive.py`.

- [ ] **Step 3: `scripts/convert_log_archive.py` 를 만든다.**

```python
#!/usr/bin/env python3
"""옛 달별 보관본을 날짜별 배치로 한 번 옮긴다 (일회성 - 다 옮기고 지운 뒤에는 이 파일도 지운다).

계획: docs/superpowers/plans/2026-10-08-log-daily-archive.md

  python3 scripts/convert_log_archive.py convert --dest /mnt/d/travel-hunter-logs --label dev   # 옮기고 검증표
  python3 scripts/convert_log_archive.py verify  --dest /mnt/d/travel-hunter-logs --label dev   # 검증표만 (읽기만)
  python3 scripts/convert_log_archive.py remove  --dest /mnt/d/travel-hunter-logs --label dev   # 다 맞을 때만 원본 삭제

- 맨 위의 <stem>-YYYY-MM[.pNN-해시].log[.gz] 를 줄 시각(KST)의 날로 나눠 YYYY-MM/<stem>-YYYY-MM-DD.p00-<해시>.log.gz 로 쓴다.
  p00 은 이 변환만 쓰는 번호다 - 그날의 새 기록(p01~, .log)보다 늘 먼저 읽힌다.
- 시각을 못 읽은 줄은 바로 앞 줄의 날로 간다(그 달의 첫 줄이면 1일).
- 평문 달 파일은 .state.json 의 확정 크기까지만 읽는다. 그 뒤는 저장 전에 멈춘 꼬리라 새 코드가 볼륨에서 다시 받았다.
- 같은 내용은 같은 이름이라 다시 돌려도 그대로다. 같은 날에 다른 내용의 p00 이 있으면 멈춘다.
- 원본은 .legacy-monthly/ 로 옮겨 둔다(trace --dir 가 두 번 읽지 않게). 지우는 것은 remove 뿐이다.
- pull_logs.py 와 같은 잠금을 잡는다. 그동안 logarchive 회차는 '잠금' 오류로 쉬고 다음 회차에 따라잡는다.
- 줄 내용은 출력하지 않는다. 날마다 줄 수·바이트·sha256 앞 12자만.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import re
import sys
from contextlib import suppress
from pathlib import Path


def _load_pull_logs():
    spec = importlib.util.spec_from_file_location("pull_logs_script", Path(__file__).with_name("pull_logs.py"))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pull_logs = _load_pull_logs()
trace = pull_logs.trace
LEGACY_DIR = ".legacy-monthly"


class ConvertError(RuntimeError):
    """변환을 멈췄다. 원본은 그대로다."""


def is_monthly(name: str) -> bool:
    match = trace.ARCHIVE_NAME.fullmatch(name)
    return bool(match) and len(match["period"]) == 7


def legacy_groups(folder: Path) -> dict[tuple[str, str], list[Path]]:
    """(stem, 달) → 옛 달별 파일, 읽는 순서대로. 맨 위와 .legacy-monthly/ 를 함께 본다 - 옮기다 멈춰도 같은 내용이 된다."""
    groups: dict[tuple[str, str], list] = {}
    for directory in (folder, folder / LEGACY_DIR):
        if not directory.is_dir():
            continue
        for path in directory.iterdir():
            if is_monthly(path.name):
                match = trace.ARCHIVE_NAME.fullmatch(path.name)
                groups.setdefault((match["stem"], match["period"]), []).append((trace.archive_order(match), path))
    return {key: [path for _, path in sorted(items)] for key, items in sorted(groups.items())}


def committed_sizes(folder: Path) -> dict[str, int]:
    state_path = folder / ".state.json"
    return json.loads(state_path.read_text("utf-8")).get(pull_logs.FILES_KEY, {}) if state_path.exists() else {}


def split_days(paths: list[Path], month: str, committed: dict[str, int]) -> tuple[dict[str, bytes], int]:
    """(날 → 그날 줄들, 읽은 전체 바이트). 평문은 확정 크기까지만 - 기록이 없으면 통째로(지우는 것보다 낫다).

    같은 달의 조각과 해시가 같은 평문은 건너뛴다 - 압축은 됐는데 원본 삭제 전에 멈춘 흔적이다(옛 archive() 와 같은 규칙).
    """
    chunk_hashes = {trace.ARCHIVE_NAME.fullmatch(p.name)["hash"] for p in paths if p.name.endswith(".gz")}
    days: dict[str, list[bytes]] = {}
    day, total = f"{month}-01", 0
    for path in paths:
        if path.name.endswith(".gz"):
            try:
                with gzip.open(path, "rb") as handle:
                    data = handle.read()  # ponytail: 한 파일씩 메모리에 - 달 파일이 수십 MB 를 넘으면 줄 단위로 바꾼다
            except (OSError, EOFError) as error:
                raise ConvertError(f"{path.name} 을 풀지 못했다({type(error).__name__}) - 멈춘다") from None
        else:
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest()[:12] in chunk_hashes:
                continue
            data = raw[:committed.get(path.name)]
        total += len(data)
        for line in re.findall(rb"[^\n]*\n", data):
            day = pull_logs.line_day(line, day)
            days.setdefault(day, []).append(line)
    return {d: b"".join(lines) for d, lines in sorted(days.items())}, total


def chunk_path(folder: Path, stem: str, day: str, digest: str) -> Path:
    return folder / day[:7] / f"{stem}-{day}.p00-{digest}.log.gz"


def convert(folder: Path) -> None:
    if not any(trace.MONTH_DIR.fullmatch(p.name) and p.is_dir() for p in folder.iterdir()):
        raise ConvertError("날짜별 폴더(YYYY-MM/)가 아직 없다 - 새 pull_logs.py 가 한 번 돈 뒤에 변환한다")
    with pull_logs.Lock(folder / ".lock"):
        committed = committed_sizes(folder)
        for (stem, month), paths in legacy_groups(folder).items():
            # 이 달의 모든 날을 먼저 확인한다 - 중간에 멈추면 이 달은 아무것도 쓰지 않는다(쓴 날만 trace 에 두 번 보이지 않게).
            targets = {}
            for day, data in split_days(paths, month, committed)[0].items():
                target = chunk_path(folder, stem, day, hashlib.sha256(data).hexdigest()[:12])
                others = [p.name for p in target.parent.glob(f"{stem}-{day}.p00-*.log.gz") if p != target]
                if others:
                    raise ConvertError(f"{day[:7]}/{others[0]} 가 이미 다른 내용이다 - 멈춘다(이 달 원본은 그대로)")
                targets[target] = data
            for target, data in targets.items():
                if not target.exists():
                    target.parent.mkdir(exist_ok=True)
                    temp = target.with_name(target.name + ".tmp")
                    with gzip.open(temp, "wb") as packed:
                        packed.write(data)
                    temp.replace(target)
            (folder / LEGACY_DIR).mkdir(exist_ok=True)
            for path in paths:  # 이 달을 다 쓴 뒤에 옮긴다
                if path.parent == folder:
                    path.replace(folder / LEGACY_DIR / path.name)


def verify(folder: Path) -> tuple[list[str], bool]:
    """원본에서 다시 나눈 날별 내용과 p00 조각을 바이트 단위로 맞춰 본다. 읽기만 한다."""
    committed = committed_sizes(folder)
    rows, ok = [], True
    for (stem, month), paths in legacy_groups(folder).items():
        days, total = split_days(paths, month, committed)
        month_lines = 0
        for day, data in days.items():
            digest = hashlib.sha256(data).hexdigest()[:12]
            try:
                same = gzip.decompress(chunk_path(folder, stem, day, digest).read_bytes()) == data
            except (OSError, EOFError):
                same = False
            ok = ok and same
            lines = data.count(b"\n")
            month_lines += lines
            rows.append(f"{stem:<12} {day}     lines={lines:<8} bytes={len(data):<10} sha={digest}  {'OK' if same else 'DIFF'}")
        whole = sum(map(len, days.values())) == total  # 줄로 나누다 흘린 바이트가 없다
        ok = ok and whole
        rows.append(f"{stem:<12} {month} 합계 lines={month_lines:<8} bytes={total:<10} {'OK' if whole else 'DIFF'}")
    return rows, ok


def remove(folder: Path) -> int:
    """검증이 다 맞고 맨 위에 옮기지 않은 원본이 없을 때만 .legacy-monthly/ 의 원본을 지운다. 지운 개수.

    .state.json 의 옛 키는 그대로 둔다 - 파일이 없으면 아무도 읽지 않는다. 상태 파일을 쓰는 프로그램을 늘리지 않는다.
    """
    with pull_logs.Lock(folder / ".lock"):
        _rows, ok = verify(folder)
        if not ok or any(is_monthly(p.name) for p in folder.iterdir()):
            raise ConvertError("검증이 다 맞지 않았거나 아직 옮기지 않은 원본이 있다 - 지우지 않는다 (verify 로 확인)")
        legacy = folder / LEGACY_DIR
        names = [p.name for p in legacy.iterdir() if is_monthly(p.name)] if legacy.is_dir() else []
        for name in names:
            (legacy / name).unlink()
        with suppress(OSError):
            legacy.rmdir()
        return len(names)


def main() -> int:
    parser = argparse.ArgumentParser(description="옛 달별 보관본을 날짜별로 한 번 옮긴다")
    parser.add_argument("command", choices=("convert", "verify", "remove"))
    parser.add_argument("--dest", default=os.environ.get("TRACE_LOCAL_DIR"), help="pull_logs.py 의 --dest")
    parser.add_argument("--label", required=True, help="보관 폴더 안의 이름 (개발서버: dev)")
    args = parser.parse_args()
    if not args.dest:
        parser.error("--dest 또는 TRACE_LOCAL_DIR 가 필요하다")
    folder = Path(args.dest) / args.label
    if not folder.is_dir():
        parser.error(f"보관 폴더가 없다: {folder}")
    try:
        if args.command == "remove":
            print(f"원본 {remove(folder)}개를 지웠다")
            return 0
        if args.command == "convert":
            convert(folder)
        rows, ok = verify(folder)
    except (ConvertError, pull_logs.PullError) as error:
        print(f"오류: {error}", file=sys.stderr)
        return 3
    print("\n".join(rows) if rows else "옛 달별 파일 없음")
    print("검증: 모두 맞음" if ok else "검증: 다른 곳이 있다 - remove 하지 말 것")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 실행.** 세 파일 명령. Expected: **119 passed** (37 + 66 + 16).

---

### Task 4: 운영 문서

**Files:** Modify `docs/deployment-cicd/log-archive-runbook.md`.

- [ ] 머리 "설계와 결정 경위" 줄에 `· 날짜별 배치: docs/superpowers/plans/2026-10-08-log-daily-archive.md` 를 붙인다.
- [ ] "구조" 그림의 ② 블록을 바꾼다:
  ```
   ② D:\travel-hunter-logs\dev\         장기. 12개월 (WSL 에서 /mnt/d/travel-hunter-logs/dev)
      2026-10\                            달 폴더
        caddy-access-2026-10-08.log         오늘 - 계속 이어 붙는다
        caddy-access-2026-10-07.p01-<해시>.log.gz   지난 날 - 다음 날 01시 넘어 압축. 늦게 온 줄은 p02 …
        backend-2026-10-07.p00-<해시>.log.gz        옛 달별 파일에서 옮긴 줄 (변환 한 번)
      .state.json                         어디까지 받았는지 (지우지 말 것)
  ```
- [ ] "조회"의 `압축된 달도 알아서 풀어 읽는다` → `압축된 날도 알아서 풀어 읽는다. 변환 전 달별 파일과 섞여 있어도 함께 읽는다.`
- [ ] "주의"의 `보관 폴더에 손으로 <stem>-YYYY-MM.log 를 넣지 말 것 …` 줄을 `보관 폴더의 달 폴더(YYYY-MM\)에 손으로 <stem>-YYYY-MM-DD.log 를 넣지 말 것. 기록에 없는 파일은 저장 전에 멈춘 흔적으로 보고 지운다.` 로 바꾸고, 그 아래에 `- 보존(--keep-months)은 달 폴더 단위다. 오래된 달 폴더 안의 보관 파일을 지우고, 다른 파일이 있으면 폴더는 남긴다.` 를 더한다.
- [ ] 새 절 "옛 달별 파일 옮기기 (한 번, 2026-10)" — 아래 "개발서버 반영" 의 3~6단계 명령과 "되돌리기"를 그대로 옮긴다. 끝에 `remove 뒤에는 convert_log_archive.py 와 그 테스트를 지우는 PR 을 올린다.`
  한 줄 더: `변환이 도중에 멈추면 그 달의 줄이 다시 convert 할 때까지 trace 에 두 번 보일 수 있다. 원인을 고치고 convert 를 다시 돌린다.`
  한 줄 더: `변환할 때 이미 --keep-months 밖인 달의 옛 파일이 있으면, 그 달의 p00 은 다음 보존 회차에 지워지고 verify 가 DIFF 가 돼 remove 가 거부된다. 그런 옛 파일은 변환 전에 사람이 지운다(개발서버 보관은 2026-09-28 부터라 지금은 해당 없음).`
- [ ] `docs/deployment-cicd/README.md` 11–12행 설명에 `날짜별 배치·옛 달별 파일 변환` 을 더한다. (`PLANS.md` 에는 로그 계획이 등록돼 있지 않다 — 손대지 않는다.)
- [ ] 확인: `git diff --check -- docs/deployment-cicd/log-archive-runbook.md`, U+FFFD 없음.

---

### Task 5: 검증

- [ ] 세 파일: Expected **119 passed**.
- [ ] 백엔드 전체 `cd backend && $PY -m pytest -q -p no:cacheprovider` — 이번 변경과 무관한 실패가 있으면 기존 실패인지(`git stash` 쓰지 말고 develop 작업 트리에서) 구분해 기록. 메모리: 내 정보 시험 6개는 쌓인 일정 탓으로 이미 실패한다.
- [ ] Python 3.10 문법: `docker run --rm -v "$PWD/scripts:/s:ro" python:3.10-alpine sh -c 'python /s/pull_logs.py --help >/dev/null && python /s/convert_log_archive.py --help >/dev/null && python /s/trace.py --help >/dev/null && echo ok'` (로컬 Docker 만. 서버 아님).
- [ ] 변이 5개만 다시 확인(일회성 작업이라 핵심만. 계획 작성 때 프로토타입에서 모두 시험이 잡았다): `SEAL_AFTER = timedelta(0)` / 평문의 확정 크기 무시(`data = raw`) / 원본 옮기기 생략 / 다른 내용의 p00 무시 / 검증 실패에도 remove. 하나라도 시험이 못 잡으면 그 시험을 고친다.
- [ ] `git diff --check`, 바뀐 파일 U+FFFD·깨진 한글 없음(UTF-8 로 읽어 확인), `git status --short` 에 의도한 파일만.
- [ ] 로컬 실제 실행(선택, 서버 아님): 임시 폴더에 옛 배치를 만들고 `pull_logs.py --source-dir <임시 볼륨> --label dev --dest <임시>` 두 번 → `convert_log_archive.py convert` → `scripts/trace --dir … --recent --since 60d | wc -l` 이 변환 전과 같다.
- [ ] 머지 준비 때 `CHECKLIST.md` 현재 상태·검증·위험 갱신, `git diff --check -- CHECKLIST.md`.

---

## 개발서버 반영 (서버 쓰기 — 단계마다 사용자 승인)

모든 확인 명령은 개수·크기·줄 수·해시만 낸다. 보관본을 `cat`/`head` 로 열지 않는다. 경로는 rev6~rev8 기준(`~/travel-hunter-onprem`, `/mnt/d/travel-hunter-logs/dev`, 컨테이너 `travel-hunter-onprem-logarchive-1`).

1. **머지·배포.** 머지는 사용자/Codex 가 한다(Claude 는 그 세션에서 사용자가 말할 때만 푸시·PR 을 열고, 머지는 하지 않는다). 머지 뒤 Jenkins develop 배포가 `~/travel-hunter-onprem` 를 갱신한다. `logarchive` 는 `./scripts` 를 바인드하므로 재시작 없이 **다음 회차(≤5분)** 부터 새 코드다. compose·env 변경 없음.
2. **새 코드가 돌았는지 (읽기만).**
   ```bash
   ssh dev-server 'docker logs --tail 3 travel-hunter-onprem-logarchive-1'          # "dev: caddy-access +…KB, backend +…KB", 오류: 없음
   ssh dev-server 'cd /mnt/d/travel-hunter-logs/dev && ls -la && ls -la 20*/'       # 2026-10/ 이 생기고 오늘 파일이 커진다
   ```
3. **변환 전 기록 (읽기만, 출력은 파일 이름·줄 수·크기·개수).**
   ```bash
   ssh dev-server 'cd /mnt/d/travel-hunter-logs/dev && for f in backend-20*.gz caddy-access-20*.gz; do [ -e "$f" ] || continue; gzip -t "$f" 2>/dev/null || echo "BROKEN $f"; done; echo gzip-check-done'
   ssh dev-server 'cd /mnt/d/travel-hunter-logs/dev && du -sh . && find . -type f | wc -l && for f in backend-20* caddy-access-20*; do [ -e "$f" ] || continue; case "$f" in *.gz) n=$(gzip -dc "$f" | wc -l);; *) n=$(wc -l < "$f");; esac; echo "$f lines=$n bytes=$(stat -c %s "$f")"; done'
   ssh dev-server 'cd ~/travel-hunter-onprem && scripts/trace --dir /mnt/d/travel-hunter-logs/dev --recent --since 60d --max-mb 1024 --color never | sort | uniq -d | wc -l'
   ```
   - `BROKEN` 이 한 줄이라도 나오면 **멈춘다**. 깨진 옛 `.gz` 가 있으면 변환은 `ConvertError` 로 그 달을 건너뛰지 않고 멈춘다 — 그 파일을 어떻게 할지(살릴 수 있는 만큼 풀기 / 버리기) 사용자가 정한다.
   - 마지막 숫자는 trace 출력에서 **두 번 이상 나온 줄 수**다(내용은 내지 않는다). 변환 전에도 0 이 아닐 수 있다 — 확정 크기 뒤 꼬리(D8)가 옛 파일과 날짜별 파일에 함께 있으면 두 번 읽힌다. 이 숫자를 기록해 두고 5단계와 비교한다. `--max-mb 1024` 는 기본 64MB 상한이 비교를 자르지 않게 한다.
   - 달 파일 크기가 수십 MB 를 넘으면 멈추고 다시 판단한다(변환은 파일 하나씩 메모리에 올린다).
4. **변환 (승인 후).** 호스트의 `python3`(3.12, rev4 확인)로 돈다. 보관 폴더는 drvfs 라 `deploy` 로 쓸 수 있다. 같은 잠금을 잡으므로 그동안 `logarchive` 회차 하나가 `오류: 다른 실행이 진행 중이다` 로 쉬고 다음 회차에 따라잡는다(`|| true` 로 루프는 계속). `잠금` 오류로 변환이 거부되면 몇 초 뒤 다시.
   ```bash
   ssh dev-server 'cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py convert --dest /mnt/d/travel-hunter-logs --label dev'
   ```
   출력은 `stem 날 lines= bytes= sha= OK|DIFF` 와 달별 `합계` 행, 마지막 `검증: 모두 맞음`. 종료 코드 1(DIFF)·3(오류)이면 멈추고 보고한다.
   시간 상한: `Lock` 은 `LOCK_STALE_SECONDS`(3600초)보다 오래된 잠금을 지운다. 변환이 한 시간을 넘으면 `logarchive` 회차가 잠금을 가져가 겹친다. 지금 크기면 수 초다 — 3단계 크기가 수백 MB 면 변환하지 말고 다시 판단한다.
5. **변환 뒤 확인 (읽기만).**
   - 검증표의 달별 `합계 lines` = 3단계에서 그 달 파일들의 줄 수 합. 단, 평문 이번 달 파일은 확정 크기 뒤 꼬리만큼, 또 같은 해시의 조각과 함께 남은 지난달 평문은 통째로 적을 수 있다(D8) — 차이가 나면 `bytes` 와 파일 이름으로 어느 쪽인지 확인해 보고.
   - ```bash
     ssh dev-server 'cd /mnt/d/travel-hunter-logs/dev && find . -name "*.p00-*.log.gz" | wc -l && ls -la .legacy-monthly && ls backend-20* caddy-access-20* 2>/dev/null | wc -l'
     ssh dev-server 'cd ~/travel-hunter-onprem && scripts/trace --dir /mnt/d/travel-hunter-logs/dev --recent --since 60d --max-mb 1024 --color never | sort | uniq -d | wc -l'
     ```
     p00 개수 = 검증표의 날 행 수, 맨 위 옛 파일 0개, 중복 줄 수는 **3단계 숫자 이하**(꼬리 중복은 변환이 확정 크기로 잘라 없어진다). 늘었으면 멈추고 보고한다. 전체 줄 수는 비교하지 않는다 — 변환이 꼬리 중복을 지워 정상적으로도 줄 수 있다.
   - 변환이 도중에 멈췄다면(오류·중단), 그 달의 줄이 다시 `convert` 할 때까지 trace 에 두 번 보일 수 있다(p00 은 썼는데 원본을 아직 옮기지 못한 경우). 원인을 고치고 `convert` 를 다시 돌리면 같은 이름이라 그대로 이어진다.
6. **원본 삭제 (하루 이상 지난 뒤, 다시 승인).** 자정+1시간을 지나 배포일이 p01 로 닫히고, `docker logs` 에 오류가 없고, 사용자가 `trace --dir` 로 아는 문의 코드 하나를 직접 확인한 뒤.
   ```bash
   ssh dev-server 'cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py verify --dest /mnt/d/travel-hunter-logs --label dev | tail -1'
   ssh dev-server 'cd ~/travel-hunter-onprem && python3 scripts/convert_log_archive.py remove --dest /mnt/d/travel-hunter-logs --label dev'
   ssh dev-server 'cd /mnt/d/travel-hunter-logs/dev && ls -a && du -sh .'
   ```
   **`remove` 가 되돌릴 수 없는 지점이다.**
7. 후속 PR: `scripts/convert_log_archive.py`·`backend/tests/test_convert_log_archive.py` 삭제, 운영 문서의 변환 절을 "완료(날짜)"로 줄인다.

## 되돌리기

- **변환만 되돌리기(`remove` 전):** `logarchive` 를 잠깐 멈추고(`cd ~/travel-hunter-onprem && docker compose -p travel-hunter-onprem --env-file deploy/.env.dev -f compose.yaml stop logarchive` — `deploy/.env.dev` 는 상대 경로라 저장소 폴더에서 돌린다), `cd /mnt/d/travel-hunter-logs/dev && mv .legacy-monthly/* . && rmdir .legacy-monthly && find 20* -name '*.p00-*.log.gz' -delete`, 다시 `start logarchive`. p00 은 변환만 만들므로 지워도 새 기록은 남는다.
- **코드 되돌리기:** 위 변환 되돌리기를 먼저 하고, develop 에서 머지 커밋을 revert → 배포. 옛 코드는 `YYYY-MM/` 를 이름 규칙상 보지 않는다 — 새 코드가 쓴 날짜별 파일은 그대로 디스크에 남고(옛 `trace --dir` 에는 안 보임, `zcat`/`grep` 으로는 보임), 다시 배포하면 다시 보인다. 받은 위치(inode)는 그대로라 옛 코드가 이어서 받는다. 옛 코드가 다시 만드는 맨 위 이번 달 파일은 확정 크기 기록과 어긋나도 작아서 잘리지 않는다(`size > committed` 일 때만 자른다).
- **`remove` 뒤:** 달별 배치로는 돌아갈 수 없다. 데이터는 날짜별 파일에 모두 있고 새 코드의 `trace` 로 읽는다.

## AWS 이전 때

- 보관 계약이 바뀐다: `<label>/YYYY-MM/<stem>-YYYY-MM-DD[.pNN-해시].log[.gz]`, 한 줄 한 JSON, 받은 순서. 날 단위는 CloudWatch Logs → S3 내보내기(날짜 접두사 `…/YYYY/MM/DD/`)와 S3 수명 주기(12개월 삭제 규칙이 `--keep-months` 를 대신)에 그대로 맞는다.
- 교체 지점은 그대로 둔다: 쓰기 쪽은 `Source`(`remote_files`·`fetch` / `local_files`·`local_fetch`), 읽기 쪽은 `trace.archive_files()`·`read_local_file()`. 이름 규칙이 `trace.py` 한곳이라 S3 객체 키 규칙으로 바꿀 때도 한곳이다.
- 지금은 CloudWatch/S3 구현을 하지 않는다(구현이 하나뿐인 추상화를 미리 두지 않는다 — rev3 결정 그대로).

## 크기

- 코드: `trace.py` +30, `pull_logs.py` ±50(대부분 같은 함수의 키 바꾸기), `convert_log_archive.py` 150(일회성, 나중에 삭제).
- 테스트: `test_pull_logs.py` 8개 재작성·5개 경로 수정, `test_trace_script.py` +5, `test_convert_log_archive.py` 16 → 119 passed.
- 시간: 구현·검증 반나절. 서버 반영은 배포 + 변환 30분, 원본 삭제는 다음 날 10분.
- 위험: (1) `_files` 키 형식이 바뀐다(`YYYY-MM/이름`) — 옛 키는 남고 새 코드는 안 읽는다. (2) 하루 파일이 늘어 연간 스트림당 ~365 조각 + 달 폴더 12개 — 보관·조회에 문제없는 수. (3) 변환은 달 파일 하나씩 메모리에 올린다(3단계 크기 확인으로 막는다). (4) 변환 중 `logarchive` 회차 한 번이 쉰다. (5) 날짜별 파일이 생긴 뒤 옛 코드로 되돌리면 그 기간이 옛 `trace` 에 안 보인다(데이터는 남음).
