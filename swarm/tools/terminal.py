import asyncio
import json
import os
import subprocess
import tempfile
from typing import Optional


class TerminalTools:
    """CLI / shell / terminal tools for the swarm."""

    @staticmethod
    async def run_command(command: str, timeout: int = 30, workdir: Optional[str] = None) -> str:
        proc = None
        try:
            cmd_parts = command if isinstance(command, list) else _split_command(command)
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir or os.getcwd(),
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            out = stdout.decode("utf-8", errors="replace") if stdout else ""
            err = stderr.decode("utf-8", errors="replace") if stderr else ""
            result = f"[exit code {proc.returncode}]\n"
            if out:
                result += f"STDOUT:\n{out[:5000]}\n"
            if err:
                result += f"STDERR:\n{err[:2000]}\n"
            return result.strip()
        except asyncio.TimeoutError:
            if proc:
                await _terminate_process(proc)
            return f"[TIMEOUT after {timeout}s] Command did not finish in time."
        except FileNotFoundError:
            return f"[ERROR] Command not found: {cmd_parts[0]}"
        except Exception as e:
            return f"[ERROR] {e}"

    @staticmethod
    async def run_script(code: str, language: str = "python", timeout: int = 60) -> str:
        suffix_map = {
            "python": ".py", "py": ".py",
            "bash": ".sh", "sh": ".sh", "shell": ".sh",
            "powershell": ".ps1", "ps1": ".ps1",
            "node": ".js", "javascript": ".js", "js": ".js",
            "ruby": ".rb", "rb": ".rb",
            "perl": ".pl", "pl": ".pl",
        }
        suffix = suffix_map.get(language.lower(), ".txt")
        interpreter_map = {
            "py": _find_interpreter("python"),
            "sh": _find_interpreter("bash"),
            "ps1": _find_interpreter("powershell"),
            "js": _find_interpreter("node"),
            "rb": _find_interpreter("ruby"),
            "pl": _find_interpreter("perl"),
        }
        interpreter = interpreter_map.get(suffix.lstrip("."), "")
        if not interpreter:
            return f"[ERROR] No interpreter found for {language}"

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    interpreter, tmp_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=timeout,
            )
            stdout, stderr = await proc.communicate()
            out = stdout.decode("utf-8", errors="replace") if stdout else ""
            err = stderr.decode("utf-8", errors="replace") if stderr else ""
            result = f"[exit code {proc.returncode}]\n"
            if out:
                result += out[:5000]
            if err:
                result += f"\nSTDERR:\n{err[:2000]}"
            return result.strip()
        except asyncio.TimeoutError:
            if "proc" in locals() and proc:
                await _terminate_process(proc)
            return f"[TIMEOUT after {timeout}s] Script execution timed out."
        except Exception as e:
            return f"[ERROR] {e}"
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    @staticmethod
    async def terminal_session(commands: list[str], shell: str = "auto", timeout: int = 120) -> str:
        if shell == "auto":
            shell = "powershell.exe" if os.name == "nt" else "bash"
        results = []
        for cmd in commands:
            result = await TerminalTools.run_command(cmd, timeout=max(30, timeout // len(commands)))
            results.append(f"$ {cmd}\n{result}")
        return "\n\n".join(results)


def _split_command(command: str) -> list[str]:
    parts = []
    current = []
    in_quote = False
    quote_char = None
    for ch in command:
        if in_quote:
            if ch == quote_char:
                in_quote = False
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        elif ch in ('"', "'"):
            in_quote = True
            quote_char = ch
        elif ch == " ":
            if current:
                parts.append("".join(current))
                current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts if parts else [command]


def _find_interpreter(name: str) -> Optional[str]:
    try:
        import shutil
        return shutil.which(name) or ""
    except Exception:
        return ""


async def _terminate_process(proc: asyncio.subprocess.Process):
    try:
        if proc.returncode is None:
            proc.kill()
    except ProcessLookupError:
        pass
    except Exception:
        pass
    try:
        await asyncio.wait_for(proc.communicate(), timeout=5)
    except Exception:
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except Exception:
            pass
    await asyncio.sleep(0)
