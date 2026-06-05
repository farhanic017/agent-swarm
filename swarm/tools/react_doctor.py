from __future__ import annotations
import asyncio
import json
import os
import re
import tempfile
from typing import Optional


class ReactDoctorTool:
    """Wrapper around `npx react-doctor@latest` for scanning React codebases.

    Scans a React project for state & effects, performance, architecture,
    security, accessibility, and correctness issues. Returns a 0-100 health
    score with structured diagnostics.
    """

    NPX_CMD = "npx"
    PACKAGE = "react-doctor@latest"

    async def scan(
        self,
        directory: str = ".",
        verbose: bool = False,
        score_only: bool = False,
        diff: Optional[str] = None,
        timeout: int = 120,
    ) -> str:
        """Run react-doctor on a project directory.

        Args:
            directory: Path to the React project root.
            verbose: Show affected files and line numbers per rule.
            score_only: Return only the numeric score (0-100).
            diff: Base branch for diff mode (only scan changed files).
            timeout: Max seconds to wait for scan completion.

        Returns:
            Formatted string with scan results.
        """
        if not os.path.isdir(directory):
            return f"Error: directory not found: {directory}"

        args = [self.NPX_CMD, self.PACKAGE, directory]

        if verbose:
            args.append("--verbose")
        if score_only:
            args.append("--score")
        if diff:
            args.extend(["--diff", diff])

        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=directory,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                # npx download noise is expected on stderr — only treat as
                # failure if stdout is empty and returncode is clearly fatal.
                if not out_text and proc.returncode > 1:
                    return (
                        f"react-doctor exited with code {proc.returncode}.\n"
                        f"stderr: {err_text[:1000]}"
                    )

            if score_only:
                score = self._extract_score(out_text)
                return str(score) if score is not None else out_text

            return self._format_output(out_text, err_text, verbose)

        except asyncio.TimeoutError:
            return (
                f"react-doctor timed out after {timeout}s. "
                "Try increasing timeout or limiting the scan scope."
            )
        except FileNotFoundError:
            return (
                "npx not found. Install Node.js >= 18 and ensure it's on your PATH."
            )
        except Exception as e:
            return f"react-doctor error: {e}"

    def _extract_score(self, text: str) -> Optional[int]:
        """Extract the 0-100 health score from output."""
        match = re.search(r"\b(\d{1,3})\s*/\s*100\b", text)
        if match:
            return int(match.group(1))
        match = re.search(r"(?:score|health)[:\s]+(\d{1,3})", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
        return None

    def _format_output(self, stdout: str, stderr: str, verbose: bool) -> str:
        """Format raw react-doctor output into a structured result."""
        lines = []

        score = self._extract_score(stdout)
        if score is not None:
            rating = "Great" if score >= 75 else "Needs work" if score >= 50 else "Critical"
            lines.append(f"React Doctor Score: {score}/100 ({rating})")

        if stdout:
            # Strip score-only lines so we don't duplicate
            remaining = re.sub(r"\d{1,3}\s*/\s*100", "", stdout).strip()
            if remaining:
                lines.append("")
                lines.append(remaining)

        if verbose:
            diagnostic_count = stdout.count("- ") if stdout else 0
            lines.append("")
            if diagnostic_count:
                lines.append(f"Found {diagnostic_count} diagnostic(s).")
            else:
                lines.append("No diagnostics reported.")

        return "\n".join(lines)

    async def install_skill(self, directory: str = ".", timeout: int = 60) -> str:
        """Install the react-doctor skill for coding agents in the project.

        Runs `npx react-doctor@latest install` to write SKILL.md, AGENTS.md,
        or .cursorrules into the project so agents learn best practices.
        """
        if not os.path.isdir(directory):
            return f"Error: directory not found: {directory}"

        try:
            proc = await asyncio.create_subprocess_exec(
                self.NPX_CMD, self.PACKAGE, "install",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=directory,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            out = stdout.decode("utf-8", errors="replace").strip()
            err = stderr.decode("utf-8", errors="replace").strip()
            if proc.returncode == 0:
                return f"React Doctor skill installed in {directory}.\n{out}"
            return (
                f"Install exited with code {proc.returncode}.\n"
                f"stderr: {err[:1000]}"
            )
        except Exception as e:
            return f"react-doctor install error: {e}"
