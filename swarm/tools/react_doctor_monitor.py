"""Always-on React Doctor — continuous background code quality monitoring.

Scans project directories for React/JS/TS/Next.js codebases on an interval
and publishes diagnostics to the Consciousness hub in real-time.

Spawns as a background asyncio task from the Orchestrator. Reports issues
as ConsciousnessEvent.diagnostic events so all agents see quality feedback.
"""

from __future__ import annotations
import asyncio
import os
import time
from pathlib import Path
from typing import Optional, Callable

from swarm.tools.react_doctor import ReactDoctorTool


class ReactDoctorMonitor:
    """Always-on background React Doctor monitor.

    Periodically scans project directories and publishes diagnostics
    via a callback (typically Consciousness.push_diagnostic).

    Usage:
        monitor = ReactDoctorMonitor(
            publish_fn=consciousness.push_diagnostic,
            interval=120,
        )
        task = asyncio.create_task(monitor.run())
        # ...
        monitor.stop()
        await task
    """

    def __init__(
        self,
        publish_fn: Optional[Callable] = None,
        interval: int = 120,
        watch_dirs: Optional[list[str]] = None,
    ):
        self._publish_fn = publish_fn
        self._interval = interval
        self._watch_dirs = watch_dirs or []
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._tool = ReactDoctorTool()
        self._last_scores: dict[str, int] = {}
        self._scan_count = 0

    def set_publish_fn(self, publish_fn: Callable):
        """Set the publish callback (typically Consciousness.push_diagnostic)."""
        self._publish_fn = publish_fn

    def add_watch_dir(self, directory: str):
        """Add a directory to the watch list."""
        if directory not in self._watch_dirs:
            self._watch_dirs.append(directory)

    def _find_react_projects(self) -> list[str]:
        """Find React/Next.js/Vite projects under watch directories."""
        indicators = [
            "package.json",
            "next.config.js", "next.config.ts", "next.config.mjs",
            "vite.config.ts", "vite.config.js",
            "react-app.d", "craco.config.js",
        ]
        projects = []
        for base_dir in self._watch_dirs:
            base = Path(base_dir)
            if not base.exists():
                continue
            for indicator in indicators:
                matches = list(base.rglob(indicator))
                for m in matches:
                    project_dir = str(m.parent)
                    if project_dir not in projects:
                        projects.append(project_dir)
        return projects

    async def _scan_once(self) -> list[dict]:
        """Run one scan cycle across all discovered projects."""
        results = []
        projects = self._find_react_projects()
        if not projects and self._watch_dirs:
            for d in self._watch_dirs:
                if os.path.isdir(d):
                    result = await self._tool.scan(
                        directory=d, verbose=False, score_only=False, timeout=90
                    )
                    self._scan_count += 1
                    score = self._tool._extract_score(result) or 0
                    prev = self._last_scores.get(d)
                    trend = ""
                    if prev is not None:
                        diff = score - prev
                        trend = f" ({'+' if diff > 0 else ''}{diff} since last scan)"
                    self._last_scores[d] = score
                    results.append({
                        "directory": d,
                        "score": score,
                        "output": result,
                        "trend": trend,
                    })
            return results

        for p in projects:
            try:
                result = await self._tool.scan(
                    directory=p, verbose=False, score_only=False, timeout=90
                )
                self._scan_count += 1
                score = self._tool._extract_score(result) or 0
                prev = self._last_scores.get(p)
                trend = ""
                if prev is not None:
                    diff = score - prev
                    trend = f" ({'+' if diff > 0 else ''}{diff} since last scan)"
                self._last_scores[p] = score
                results.append({
                    "directory": p,
                    "score": score,
                    "output": result,
                    "trend": trend,
                })
            except Exception:
                continue

        return results

    async def run(self):
        """Main background loop. Runs scans on interval, publishes diagnostics."""
        self._running = True
        if not self._publish_fn:
            return

        while self._running:
            try:
                results = await self._scan_once()
                for r in results:
                    dir_name = os.path.basename(r["directory"])
                    severity = "error" if r["score"] < 50 else "warning" if r["score"] < 75 else "info"
                    await self._publish_fn(
                        source="react_doctor_monitor",
                        severity=severity,
                        message=f"{dir_name}: {r['score']}/100{r['trend']}",
                        detail={
                            "directory": r["directory"],
                            "score": r["score"],
                            "full_output": r["output"][:1000],
                        },
                    )
            except Exception as e:
                if self._publish_fn:
                    await self._publish_fn(
                        source="react_doctor_monitor",
                        severity="error",
                        message=f"Scan failed: {e}",
                    )

            if self._running:
                for _ in range(self._interval):
                    if not self._running:
                        break
                    await asyncio.sleep(1)

    async def run_once(self) -> str:
        """Run a single scan cycle and return results summary."""
        results = await self._scan_once()
        if not results:
            return "No React/JS projects found to scan."
        lines = [f"React Doctor scan complete ({len(results)} project(s)):"]
        for r in results:
            rating = "Great" if r["score"] >= 75 else "Needs work" if r["score"] >= 50 else "Critical"
            lines.append(f"  {r['directory']}: {r['score']}/100 ({rating}){r['trend']}")
        return "\n".join(lines)

    def stop(self):
        """Signal the background loop to stop."""
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        return {
            "running": self._running,
            "scans_performed": self._scan_count,
            "watch_dirs": list(self._watch_dirs),
            "last_scores": dict(self._last_scores),
            "interval_seconds": self._interval,
        }
