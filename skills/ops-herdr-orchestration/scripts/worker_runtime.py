#!/usr/bin/env python3
"""Shared bounded I/O for the Herdr worker dispatcher and watcher."""

from __future__ import annotations

import os
import subprocess


HERDR_TIMEOUT_SECONDS = 10


def herdr(
    session: str,
    *args: str,
    timeout_seconds: int = HERDR_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    command = ["herdr", "--session", session, *args]
    env = os.environ.copy()
    env["IPSE_HERDR_DISPATCH"] = "1"
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as error:
        return subprocess.CompletedProcess(
            command,
            124,
            stdout=error.stdout or "",
            stderr=f"herdr timed out after {timeout_seconds}s",
        )
