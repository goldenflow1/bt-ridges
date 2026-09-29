"""Subprocess execution with timeouts, process groups and bounded output buffering."""

from __future__ import annotations

import os
import re
import signal
import subprocess
import threading
from typing import List, Optional, Sequence, Set, Union

ERROR_LINE = re.compile(r"(error|fail|exception|traceback|assert|panic|fatal)", re.IGNORECASE)
HEAD_BYTES = 256 * 1024
TAIL_BYTES = 768 * 1024


class ProcResult:
    def __init__(self, code: int, output: str, timed_out: bool = False):
        self.code = code
        self.output = output
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.code == 0 and not self.timed_out


class BoundedBuffer:
    """Keeps the first HEAD_BYTES and the last TAIL_BYTES of a stream; memory stays bounded."""

    def __init__(self, head: int = HEAD_BYTES, tail: int = TAIL_BYTES):
        self.head_limit, self.tail_limit = head, tail
        self.head = bytearray()
        self.tail = bytearray()
        self.dropped = 0

    def feed(self, chunk: bytes) -> None:
        room = self.head_limit - len(self.head)
        if room > 0:
            self.head += chunk[:room]
            chunk = chunk[room:]
        if chunk:
            self.tail += chunk
            excess = len(self.tail) - self.tail_limit
            if excess > 0:
                del self.tail[:excess]
                self.dropped += excess

    def text(self) -> str:
        middle = f"\n[... {self.dropped} bytes of output dropped ...]\n".encode() if self.dropped else b""
        return (bytes(self.head) + middle + bytes(self.tail)).decode("utf-8", "replace")


class ProcessRunner:
    """Runs commands in their own process group so they can always be killed."""

    def __init__(self, cwd: str):
        self.cwd = cwd
        self._live: Set[int] = set()

    def run(
        self,
        cmd: Union[str, Sequence[str]],
        timeout: float = 120.0,
        cwd: Optional[str] = None,
        env: Optional[dict] = None,
        stdin: Optional[str] = None,
    ) -> ProcResult:
        shell = isinstance(cmd, str)
        merged_env = dict(os.environ)
        merged_env.setdefault("PYTHONDONTWRITEBYTECODE", "1")
        if env:
            merged_env.update(env)
        proc = subprocess.Popen(
            cmd,
            shell=shell,
            cwd=cwd or self.cwd,
            env=merged_env,
            stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            executable="/bin/bash" if shell else None,
        )
        self._live.add(proc.pid)
        buffer = BoundedBuffer()

        def pump() -> None:
            while True:
                chunk = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else proc.stdout.read(65536)
                if not chunk:
                    break
                buffer.feed(chunk)

        def feed_stdin() -> None:
            try:
                proc.stdin.write(stdin.encode())
                proc.stdin.close()
            except (BrokenPipeError, OSError, ValueError):
                pass

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        if stdin is not None:
            threading.Thread(target=feed_stdin, daemon=True).start()
        timed_out = False
        try:
            proc.wait(timeout=max(0.1, timeout))
        except subprocess.TimeoutExpired:
            timed_out = True
        finally:
            _kill_group(proc.pid)
            self._live.discard(proc.pid)
        reader.join(timeout=5)
        try:
            proc.stdout.close()
        except OSError:
            pass
        if timed_out:
            proc.wait(timeout=5)
            return ProcResult(124, buffer.text() + f"\n[timed out after {timeout:.0f}s]", True)
        return ProcResult(proc.returncode, buffer.text())

    def kill_all(self) -> None:
        for pid in list(self._live):
            _kill_group(pid)
        self._live.clear()


def run_full(args: Sequence[str], cwd: str, timeout: float = 120.0, env: Optional[dict] = None,
             stdin: Optional[str] = None) -> ProcResult:
    """Unbounded capture for trusted internal commands whose output must stay exact (git diff, git show)."""
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    try:
        done = subprocess.run(
            list(args), cwd=cwd, env=merged_env, input=stdin.encode() if stdin is not None else None,
            capture_output=True, timeout=timeout, start_new_session=True,
        )
    except subprocess.TimeoutExpired:
        return ProcResult(124, f"[timed out after {timeout:.0f}s]", True)
    out = done.stdout.decode("utf-8", "replace")
    if done.returncode:
        out += done.stderr.decode("utf-8", "replace")
    return ProcResult(done.returncode, out)


def _kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def cap_output(text: str, limit: int = 6000) -> str:
    """Keep the head, the tail and error-looking lines from the middle."""
    if len(text) <= limit:
        return text
    head_len = limit // 3
    tail_len = limit // 3
    head, middle, tail = text[:head_len], text[head_len:-tail_len], text[-tail_len:]
    picked: List[str] = []
    budget = limit - head_len - tail_len - 80
    for line in middle.splitlines():
        if ERROR_LINE.search(line) and budget > len(line):
            picked.append(line)
            budget -= len(line) + 1
    omitted = len(middle) - sum(len(line) + 1 for line in picked)
    return head + f"\n[... {omitted} chars omitted ...]\n" + "\n".join(picked) + "\n" + tail
