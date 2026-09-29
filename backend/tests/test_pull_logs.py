"""scripts/pull_logs.py — 서버 볼륨 로그를 개발 PC 로 증분 복사.

계획: docs/superpowers/plans/2026-09-28-pull-logs-to-local.md
Docker 없이 돈다. docker exec 를 가짜 원격 디렉터리로 바꿔 stat · tail|head 에 답한다.
"""

from __future__ import annotations

import gzip
import importlib.util
import json
import os
import re
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pull_logs.py"


def _load():
    spec = importlib.util.spec_from_file_location("pull_logs_script", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


pull_logs = _load()
KST = timezone(timedelta(hours=9))
FETCH = re.compile(
    r"^f='/var/log/travelhunter/([^']+)'; \[ -e \"\$f\" \] \|\| exit 4; exec 3< \"\$f\" \|\| exit 3; "
    r"\[ \"\$\(stat -Lc %i /proc/\$\$/fd/3\)\" = (\d+) \] \|\| exit 4; "
    r"tail -c \+(\d+) <&3 \| head -c (\d+)$"
)


class Remote:
    """서버 볼륨 흉내. 이름 → [inode, 내용]."""

    def __init__(self) -> None:
        self.files: dict[str, list] = {}
        self.next_inode = 100
        self.broken: set[str] = set()  # 이 컨테이너는 exec 실패
        self.fail_fetch = False
        self.before_fetch = None  # 목록 조회와 가져오기 사이에 일어날 일(회전 등)
        self.commands: list[str] = []

    def write(self, name: str, text: str) -> None:
        if name not in self.files:
            self.next_inode += 1
            self.files[name] = [str(self.next_inode), b""]
        self.files[name][1] += text.encode("utf-8")

    def rotate_backend(self) -> None:
        """RotatingFileHandler 처럼 .N → .N+1, 현재 → .1, 새 현재 파일. inode 는 이름을 따라가지 않는다."""
        numbered = sorted((n for n in self.files if re.fullmatch(r"backend\.log\.\d+", n)),
                          key=lambda n: int(n.rsplit(".", 1)[1]), reverse=True)
        for name in numbered:
            index = int(name.rsplit(".", 1)[1])
            self.files[f"backend.log.{index + 1}"] = self.files.pop(name)
        self.files["backend.log.1"] = self.files.pop("backend.log")

    def __call__(self, cmd, **kwargs):
        container, script = cmd[2], cmd[-1]
        self.commands.append(script)
        binary = "encoding" not in kwargs
        if container in self.broken:
            err = f"container {container} is not running"
            return SimpleNamespace(returncode=1, stdout=b"" if binary else "", stderr=err.encode() if binary else err)
        if script.startswith("cd /var/log/travelhunter && stat"):
            if not self.files:
                return SimpleNamespace(returncode=1, stdout="", stderr="stat: can't stat '*': No such file or directory")
            # 셸 glob 처럼 이름순으로 준다(backend.log, .1, .10, .2 ...). 시간순 정렬은 스크립트의 몫이다.
            lines = [f"{inode} {len(data)} {name}" for name, (inode, data) in sorted(self.files.items())]
            return SimpleNamespace(returncode=0, stdout="\n".join(lines) + "\n", stderr="")
        match = FETCH.match(script)
        assert match, script
        if self.before_fetch:
            hook, self.before_fetch = self.before_fetch, None
            hook()
        name, inode, start, length = match.group(1), match.group(2), int(match.group(3)), int(match.group(4))
        if name not in self.files:
            return SimpleNamespace(returncode=4, stdout=b"", stderr=b"")  # [ -e ] 실패 - 회전 중 잠깐 없다
        if self.fail_fetch:
            # 실제 sh: 있는데 exec 3< 가 못 열면 메시지와 함께 0 이 아닌 코드로 끝난다
            return SimpleNamespace(returncode=2, stdout=b"", stderr=f"sh: can't open '{name}'".encode())
        if self.files[name][0] != inode:
            return SimpleNamespace(returncode=4, stdout=b"", stderr=b"")  # 그 사이 이름이 다른 파일로 바뀌었다
        data = self.files[name][1]
        return SimpleNamespace(returncode=0, stdout=data[start - 1:start - 1 + length], stderr=b"")


@pytest.fixture
def remote(monkeypatch):
    fake = Remote()
    monkeypatch.setattr(subprocess, "run", fake)
    return fake


NOW = datetime(2026, 9, 28, 12, 0, tzinfo=KST)


def run(dest: Path, max_bytes: int = 1024 * 1024, containers=("caddy", "backend"), **kwargs):
    kwargs.setdefault("now", NOW)
    return pull_logs.pull("dev", dest, max_bytes, list(containers), **kwargs)


def parts(dest: Path, stem: str, month: str) -> list[Path]:
    return sorted((dest / "dev").glob(f"{stem}-{month}.p*.log.gz"))


def local(dest: Path, stem: str, month: str = "2026-09") -> str:
    """보관본 한 달치. 압축 조각(번호순)과 그 뒤 붙은 .log 를 순서대로 합친다."""
    text = "".join(gzip.decompress(path.read_bytes()).decode("utf-8") for path in parts(dest, stem, month))
    plain = dest / "dev" / f"{stem}-{month}.log"
    if plain.exists():
        text += plain.read_bytes().decode("utf-8")
    return text


def json_line(ts: str, path: str = "/api/x") -> str:
    return json.dumps({"ts": ts, "kind": "access", "request_id": "r1", "method": "GET", "path": path,
                       "status": 200, "duration_ms": 1}) + "\n"


def state(dest: Path) -> dict:
    return json.loads((dest / "dev" / ".state.json").read_text("utf-8"))


# ----------------------------------------------------------------------------- 기본
def test_first_run_copies_everything_oldest_first(remote, tmp_path):
    remote.write("backend.log.2", "b1\n")
    remote.write("backend.log.1", "b2\n")
    remote.write("backend.log", "b3\n")
    remote.write("caddy-access-2026-09-27T01-00-00.000-size.log", "c1\n")
    remote.write("caddy-access.log", "c2\n")
    run(tmp_path)
    assert local(tmp_path, "backend") == "b1\nb2\nb3\n"
    assert local(tmp_path, "caddy-access") == "c1\nc2\n"


def test_second_run_takes_only_new_lines(remote, tmp_path):
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    remote.write("caddy-access.log", "b\n")
    result = run(tmp_path)
    assert local(tmp_path, "caddy-access") == "a\nb\n"
    assert result["caddy-access"] == 2
    assert any("tail -c +3 <&3" in cmd for cmd in remote.commands), "받은 위치 다음부터 요청한다"


def test_backend_rotation_between_runs_loses_and_repeats_nothing(remote, tmp_path):
    remote.write("backend.log", "a\nb\n")
    run(tmp_path)
    remote.write("backend.log", "c\n")  # 받기 전에 추가되고
    remote.rotate_backend()             # 회전돼서 이름이 backend.log.1 로 바뀌었다
    remote.write("backend.log", "d\n")
    run(tmp_path)
    assert local(tmp_path, "backend") == "a\nb\nc\nd\n"


def test_half_written_line_waits_for_the_next_run(remote, tmp_path):
    remote.write("caddy-access.log", "x\npar")
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "x\n"
    remote.write("caddy-access.log", "tial\n")
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "x\npartial\n"


def test_empty_volume_is_not_an_error(remote, tmp_path):
    assert run(tmp_path) == {"caddy-access": 0, "backend": 0}


def test_budget_caps_one_run_and_the_next_run_continues(remote, tmp_path):
    remote.write("caddy-access.log", "".join(f"{i:03d}\n" for i in range(10)))
    run(tmp_path, max_bytes=12)
    assert local(tmp_path, "caddy-access") == "000\n001\n002\n"
    run(tmp_path)
    assert local(tmp_path, "caddy-access").count("\n") == 10


def test_deleted_rotations_are_forgotten(remote, tmp_path):
    remote.write("backend.log.1", "old\n")
    remote.write("backend.log", "new\n")
    run(tmp_path)
    old_inode = remote.files["backend.log.1"][0]
    del remote.files["backend.log.1"]
    run(tmp_path)
    assert old_inode not in state(tmp_path)["backend"]


def test_reused_inode_with_smaller_size_starts_over(remote, tmp_path):
    remote.write("caddy-access.log", "aaaa\nbbbb\n")
    run(tmp_path)
    inode = remote.files["caddy-access.log"][0]
    remote.files["caddy-access.log"] = [inode, b"z\n"]  # 같은 inode, 더 작은 새 파일
    run(tmp_path)
    assert local(tmp_path, "caddy-access").endswith("z\n")


# ----------------------------------------------------------------------------- 안전
def test_shell_unsafe_names_are_never_requested(remote, tmp_path):
    remote.write("caddy-access-x'; rm -rf ~ #.log", "evil\n")
    remote.write("caddy-access.log", "ok\n")
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "ok\n"
    assert not any("rm -rf" in cmd for cmd in remote.commands)


def test_failed_fetch_changes_nothing_and_raises(remote, tmp_path):
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    before = state(tmp_path)
    remote.write("caddy-access.log", "b\n")
    remote.fail_fetch = True
    with pytest.raises(pull_logs.PullError):
        run(tmp_path)
    assert state(tmp_path) == before and local(tmp_path, "caddy-access") == "a\n"
    remote.fail_fetch = False
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "a\nb\n"


def test_falls_back_to_the_other_container(remote, tmp_path):
    remote.write("caddy-access.log", "a\n")
    remote.broken.add("caddy")
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "a\n"


def test_every_container_failing_is_an_error_not_empty(remote, tmp_path):
    remote.broken.update({"caddy", "backend"})
    with pytest.raises(pull_logs.PullError) as error:
        run(tmp_path)
    assert "caddy:" in str(error.value) and "backend:" in str(error.value)


def test_a_running_pull_blocks_another(remote, tmp_path):
    (tmp_path / "dev").mkdir()
    (tmp_path / "dev" / ".lock").touch()
    with pytest.raises(pull_logs.PullError, match="잠금"):
        run(tmp_path)


def test_a_stale_lock_is_cleared(remote, tmp_path):
    lock = tmp_path / "dev" / ".lock"
    lock.parent.mkdir()
    lock.touch()
    old = time.time() - pull_logs.LOCK_STALE_SECONDS - 10
    os.utime(lock, (old, old))
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "a\n" and not lock.exists()


# ----------------------------------------------------------------------------- 장기 보관(달별·압축·보존)
def test_lines_go_to_the_month_of_their_own_time(remote, tmp_path):
    remote.write("backend.log", json_line("2026-08-31T23:59:00+09:00", "/aug") + json_line("2026-09-01T00:01:00+09:00", "/sep"))
    run(tmp_path)
    assert "/aug" in local(tmp_path, "backend", "2026-08") and "/sep" not in local(tmp_path, "backend", "2026-08")
    assert "/sep" in local(tmp_path, "backend", "2026-09")


def test_caddy_epoch_time_is_split_in_kst(remote, tmp_path):
    # 2026-08-31T15:30Z = 2026-09-01 00:30 KST - UTC 로 나누면 8월로 잘못 간다.
    epoch = datetime(2026, 8, 31, 15, 30, tzinfo=timezone.utc).timestamp()
    remote.write("caddy-access.log", json.dumps({"ts": epoch, "status": 200}) + "\n")
    run(tmp_path)
    assert local(tmp_path, "caddy-access", "2026-09") and not local(tmp_path, "caddy-access", "2026-08")


def test_past_months_are_compressed_and_the_current_month_is_not(remote, tmp_path):
    remote.write("backend.log", json_line("2026-08-10T10:00:00+09:00") + json_line("2026-09-10T10:00:00+09:00"))
    run(tmp_path)
    folder = tmp_path / "dev"
    assert len(parts(tmp_path, "backend", "2026-08")) == 1 and not (folder / "backend-2026-08.log").exists()
    assert (folder / "backend-2026-09.log").exists() and not parts(tmp_path, "backend", "2026-09")


def test_late_lines_for_a_compressed_month_are_kept(remote, tmp_path):
    remote.write("backend.log", json_line("2026-08-10T10:00:00+09:00", "/first"))
    run(tmp_path)
    remote.write("backend.log", json_line("2026-08-31T23:58:00+09:00", "/late"))  # 늦게 도착한 8월 줄
    run(tmp_path)
    august = local(tmp_path, "backend", "2026-08")
    assert august.index("/first") < august.index("/late")
    assert [p.name.split(".")[1][:3] for p in parts(tmp_path, "backend", "2026-08")] == ["p01", "p02"]
    assert not (tmp_path / "dev" / "backend-2026-08.log").exists()


def test_month_rollover_compresses_last_month_on_the_next_run(remote, tmp_path):
    remote.write("backend.log", json_line("2026-09-30T23:00:00+09:00"))
    run(tmp_path)
    assert (tmp_path / "dev" / "backend-2026-09.log").exists()
    run(tmp_path, now=datetime(2026, 10, 1, 0, 5, tzinfo=KST))
    assert len(parts(tmp_path, "backend", "2026-09")) == 1
    assert not (tmp_path / "dev" / "backend-2026-09.log").exists()


def test_months_older_than_the_keep_window_are_deleted(remote, tmp_path):
    folder = tmp_path / "dev"
    folder.mkdir()
    for month in ("2025-08", "2025-09", "2025-10"):
        (folder / f"backend-{month}.log.gz").write_bytes(gzip.compress(b"old\n"))
    (folder / "notes.txt").write_text("keep me", "utf-8")
    run(tmp_path, keep_months=12)  # 2026-09 기준 12개월 = 2025-10 ~ 2026-09
    names = sorted(p.name for p in folder.iterdir())
    assert "backend-2025-08.log.gz" not in names and "backend-2025-09.log.gz" not in names
    assert "backend-2025-10.log.gz" in names and "notes.txt" in names, "보관 형식이 아닌 파일은 건드리지 않는다"


def test_label_names_the_archive_folder(remote, tmp_path):
    remote.write("caddy-access.log", "a\n")
    pull_logs.pull("local", tmp_path, 1024, ["caddy"], label="dev", now=NOW)
    assert (tmp_path / "dev" / "caddy-access-2026-09.log").exists()
    assert not (tmp_path / "local").exists()


# ----------------------------------------------------------------------------- 누락·중복 방지 (rev5)
def test_rotation_between_listing_and_fetch_loses_and_repeats_nothing(remote, tmp_path):
    """리뷰어 재현 시나리오: 목록을 받은 뒤 가져오기 전에 backend 가 또 회전한다."""
    remote.write("backend.log", "a\nb\n")
    run(tmp_path)
    remote.write("backend.log", "c\n")
    remote.rotate_backend()
    remote.write("backend.log", "ddddd\n")

    def rotate_again():
        remote.write("backend.log", "e\n")
        remote.rotate_backend()

    remote.before_fetch = rotate_again
    only = ("backend",)  # 다른 컨테이너로 넘어가 우연히 맞는 일이 없게 하나만
    run(tmp_path, containers=only)  # 이번엔 이름이 바뀐 파일을 건너뛴다(오류가 아니다)
    run(tmp_path, containers=only)  # 다음 실행이 나머지를 받는다
    assert local(tmp_path, "backend") == "a\nb\nc\nddddd\ne\n"


def test_append_without_saved_state_is_rolled_back(remote, tmp_path):
    """붙인 뒤 위치를 저장하기 전에 멈춘 흔적(확정 크기보다 긴 꼬리)은 되돌린다."""
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    remote.write("caddy-access.log", "b\n")
    with open(tmp_path / "dev" / "caddy-access-2026-09.log", "ab") as handle:
        handle.write(b"b\n")  # 붙였지만 저장은 못 했다
    run(tmp_path)
    assert local(tmp_path, "caddy-access") == "a\nb\n"


def test_an_untracked_archive_file_from_a_crash_is_removed(remote, tmp_path):
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    (tmp_path / "dev" / "backend-2026-09.log").write_bytes(b"never saved\n")  # 만들고 저장 전에 멈췄다
    run(tmp_path)
    assert not (tmp_path / "dev" / "backend-2026-09.log").exists()


def test_missing_state_keeps_existing_archive(remote, tmp_path):
    """상태 파일이 지워져도 보관본을 지우지 않는다(다시 받아 중복은 생길 수 있다)."""
    remote.write("caddy-access.log", "a\n")
    run(tmp_path)
    (tmp_path / "dev" / ".state.json").unlink()
    run(tmp_path)
    assert local(tmp_path, "caddy-access").startswith("a\n")


def test_interrupted_compression_is_finished_without_duplicates(remote, tmp_path):
    """압축본은 만들었는데 원본을 못 지우고 멈췄다. 다음 실행은 같은 해시를 찾고 원본만 지운다."""
    folder = tmp_path / "dev"
    remote.write("backend.log", json_line("2026-08-10T10:00:00+09:00", "/aug"))
    run(tmp_path)
    [packed] = parts(tmp_path, "backend", "2026-08")
    restored = gzip.decompress(packed.read_bytes())
    (folder / "backend-2026-08.log").write_bytes(restored)  # 원본이 남아 있는 상태로 되돌린다
    state_data = state(tmp_path)
    state_data["_files"]["backend-2026-08.log"] = len(restored)
    (folder / ".state.json").write_text(json.dumps(state_data), "utf-8")
    # 그 사이 8월 줄이 늦게 도착한다. 압축을 먼저 마무리하지 않으면 원본+새 줄이 새 조각이 돼 /aug 가 두 번 남는다.
    remote.write("backend.log", json_line("2026-08-31T23:59:00+09:00", "/late"))
    run(tmp_path)
    august = local(tmp_path, "backend", "2026-08")
    assert august.count("/aug") == 1 and august.count("/late") == 1


def test_only_log_stems_are_archived_or_deleted(remote, tmp_path):
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "notes-2024-01.log").write_text("mine", "utf-8")
    run(tmp_path)
    assert (folder / "notes-2024-01.log").exists()


# ----------------------------------------------------------------------------- 볼륨 직접 읽기 (logarchive 컨테이너, rev7)
@pytest.fixture
def volume(tmp_path, monkeypatch):
    """실제 파일로 된 볼륨. docker 를 부르면 실패한다."""
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("--source-dir 은 docker 를 쓰지 않는다"))
    folder = tmp_path / "volume"
    folder.mkdir()
    return folder


def append(path: Path, text: str) -> None:
    with open(path, "ab") as handle:
        handle.write(text.encode())


def rotate(folder: Path) -> None:
    """RotatingFileHandler 처럼: .N → .N+1, 현재 → .1, 새 현재 파일."""
    numbered = sorted((p for p in folder.glob("backend.log.*")), key=lambda p: int(p.name.rsplit(".", 1)[1]), reverse=True)
    for path in numbered:
        os.replace(path, folder / f"backend.log.{int(path.name.rsplit('.', 1)[1]) + 1}")
    os.replace(folder / "backend.log", folder / "backend.log.1")
    (folder / "backend.log").touch()


def run_dir(volume: Path, dest: Path, **kwargs):
    kwargs.setdefault("now", NOW)
    return pull_logs.pull("local", dest, 1024 * 1024, [], label="dev", source_dir=str(volume), **kwargs)


def test_directory_source_takes_only_new_lines(volume, tmp_path):
    append(volume / "caddy-access.log", "a\n")
    run_dir(volume, tmp_path)
    append(volume / "caddy-access.log", "b\npart")
    run_dir(volume, tmp_path)
    assert local(tmp_path, "caddy-access") == "a\nb\n", "반쪽 줄은 다음 회차로"


def test_directory_source_follows_real_rotation(volume, tmp_path):
    append(volume / "backend.log", "a\nb\n")
    run_dir(volume, tmp_path)
    append(volume / "backend.log", "c\n")
    rotate(volume)
    append(volume / "backend.log", "d\n")
    run_dir(volume, tmp_path)
    assert local(tmp_path, "backend") == "a\nb\nc\nd\n"


def test_directory_source_skips_a_file_rotated_between_listing_and_read(volume, tmp_path, monkeypatch):
    append(volume / "backend.log", "a\n")
    run_dir(volume, tmp_path)
    append(volume / "backend.log", "b\n")
    original = pull_logs.local_fetch
    calls = []

    def rotate_first(*args):
        if not calls:
            append(volume / "backend.log", "c\n")
            rotate(volume)  # 목록은 옛 inode 를 backend.log 로 봤는데 이제 다른 파일이다
        calls.append(args)
        return original(*args)

    monkeypatch.setattr(pull_logs, "local_fetch", rotate_first)
    run_dir(volume, tmp_path)
    monkeypatch.setattr(pull_logs, "local_fetch", original)
    run_dir(volume, tmp_path)
    assert local(tmp_path, "backend") == "a\nb\nc\n"


def test_directory_source_state_continues_from_docker_mode_inodes(volume, tmp_path):
    """cron(docker exec)에서 컨테이너(직접 읽기)로 바꿔도 같은 inode 라 이어받는다."""
    append(volume / "caddy-access.log", "old\n")
    inode = str(os.stat(volume / "caddy-access.log").st_ino)
    folder = tmp_path / "dev"
    folder.mkdir()
    (folder / "caddy-access-2026-09.log").write_bytes(b"old\n")
    (folder / ".state.json").write_text(json.dumps({"_files": {"caddy-access-2026-09.log": 4},
                                                     "caddy-access": {inode: 4}}), "utf-8")
    append(volume / "caddy-access.log", "new\n")
    run_dir(volume, tmp_path)
    assert local(tmp_path, "caddy-access") == "old\nnew\n"


def test_directory_source_ignores_links_and_odd_names(volume, tmp_path):
    append(volume / "caddy-access.log", "ok\n")
    secret = tmp_path / "secret.txt"
    secret.write_text("do not copy\n", "utf-8")
    try:
        os.symlink(secret, volume / "caddy-access-2026-01-01T00-00-00.000-size.log")
    except (OSError, NotImplementedError):
        pass  # Windows 에서 링크를 못 만들면 이름 규칙만 본다
    try:
        (volume / "caddy-access.log\n").write_bytes(b"evil\n")  # 줄바꿈이 끝에 붙은 이름(Linux 에서만 만들어진다)
    except OSError:
        pass
    run_dir(volume, tmp_path)
    assert local(tmp_path, "caddy-access") == "ok\n"
    assert pull_logs._name_pattern("backend").fullmatch("backend.log\n") is None


def test_directory_source_missing_volume_is_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("docker 를 쓰지 않는다"))
    with pytest.raises(pull_logs.PullError):
        run_dir(tmp_path / "no-volume", tmp_path)


def test_local_fetch_returns_what_exists_on_a_short_file(volume):
    append(volume / "backend.log", "abc\n")
    inode = str(os.stat(volume / "backend.log").st_ino)
    assert pull_logs.local_fetch(str(volume), "backend.log", inode, 1, 100) == b"bc\n"
    assert pull_logs.local_fetch(str(volume), "backend.log", "0", 0, 10) is None, "다른 inode 면 읽지 않는다"
    assert pull_logs.local_fetch(str(volume), "gone.log", inode, 0, 10) is None, "사라진 이름은 건너뛴다"


def test_a_file_that_vanishes_after_listing_is_skipped(volume, monkeypatch):
    append(volume / "backend.log", "a\n")
    real = os.listdir
    monkeypatch.setattr(pull_logs.os, "listdir", lambda path: real(path) + ["backend.log.1"])  # 목록엔 있고 실제론 없다
    assert [name for _, _, name in pull_logs.local_files(str(volume), "backend")] == ["backend.log"]
