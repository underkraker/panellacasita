import subprocess


def run_command(cmd: list[str], timeout: int = 30) -> dict:
    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
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
    except Exception as exc:
        return {
            "ok": False,
            "command": cmd,
            "stdout": "",
            "stderr": str(exc),
            "returncode": -1,
        }
