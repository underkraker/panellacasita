import subprocess


def run_command(cmd: list[str], timeout: int = 30, input_data: str | None = None) -> dict:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_data,
        )
        return {
            "ok": True,
            "command": cmd,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "returncode": result.returncode,
        }
    except subprocess.CalledProcessError as exc:
        return {
            "ok": False,
            "command": cmd,
            "stdout": (exc.stdout or "").strip(),
            "stderr": (exc.stderr or "").strip(),
            "returncode": exc.returncode,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "command": cmd,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "").strip() if isinstance(exc.stderr, str) else "Command timeout",
            "returncode": 124,
        }
    except Exception as exc:
        return {
            "ok": False,
            "command": cmd,
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
        }
