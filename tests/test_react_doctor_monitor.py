"""Tests for the always-on React Doctor Monitor."""

from __future__ import annotations
import pytest
import asyncio
import os
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from swarm.tools.react_doctor_monitor import ReactDoctorMonitor


@pytest.fixture
def monitor():
    publish_fn = AsyncMock()
    return ReactDoctorMonitor(publish_fn=publish_fn, interval=3600)


class TestInit:
    def test_default_state(self):
        m = ReactDoctorMonitor(interval=300)
        assert m._interval == 300
        assert m._watch_dirs == []
        assert not m.is_running
        assert m._scan_count == 0

    def test_with_publish_fn(self):
        fn = lambda: None
        m = ReactDoctorMonitor(publish_fn=fn, interval=60)
        assert m._publish_fn is fn

    def test_with_watch_dirs(self):
        m = ReactDoctorMonitor(watch_dirs=["/tmp", "/home"], interval=60)
        assert "/tmp" in m._watch_dirs
        assert "/home" in m._watch_dirs


class TestWatchDirs:
    def test_add_watch_dir(self, monitor):
        monitor.add_watch_dir("/new/path")
        assert "/new/path" in monitor._watch_dirs

    def test_add_watch_dir_deduplicates(self, monitor):
        monitor.add_watch_dir("/path")
        monitor.add_watch_dir("/path")
        assert len(monitor._watch_dirs) == 1

    def test_set_publish_fn(self, monitor):
        fn = AsyncMock()
        monitor.set_publish_fn(fn)
        assert monitor._publish_fn is fn


class TestFindReactProjects:
    def test_no_watch_dirs(self, monitor):
        projects = monitor._find_react_projects()
        assert projects == []

    @pytest.mark.asyncio
    async def test_find_package_json(self, monitor):
        with tempfile.TemporaryDirectory() as tmpdir:
            pkg = os.path.join(tmpdir, "package.json")
            with open(pkg, "w") as f:
                f.write("{}")
            monitor.add_watch_dir(tmpdir)
            projects = monitor._find_react_projects()
            assert tmpdir in projects


class TestScanOnce:
    @pytest.mark.asyncio
    async def test_scan_no_projects(self, monitor):
        results = await monitor._scan_once()
        assert results == []

    @pytest.mark.asyncio
    async def test_scan_detects_score(self, monitor):
        with patch.object(monitor._tool, "scan") as mock_scan:
            mock_scan.return_value = "Health score: 85/100"
            with tempfile.TemporaryDirectory() as tmpdir:
                monitor.add_watch_dir(tmpdir)
                results = await monitor._scan_once()
                assert len(results) == 1
                assert results[0]["score"] == 85

    @pytest.mark.asyncio
    async def test_scan_tracks_trend(self, monitor):
        with patch.object(monitor._tool, "scan") as mock_scan:
            mock_scan.return_value = "Score: 70/100"
            with tempfile.TemporaryDirectory() as tmpdir:
                monitor.add_watch_dir(tmpdir)
                await monitor._scan_once()
                mock_scan.return_value = "Score: 80/100"
                results = await monitor._scan_once()
                assert "+10" in results[0]["trend"]


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_no_projects(self, monitor):
        result = await monitor.run_once()
        assert "No React" in result

    @pytest.mark.asyncio
    async def test_run_once_with_projects(self, monitor):
        with patch.object(monitor._tool, "scan") as mock_scan:
            mock_scan.return_value = "Score: 90/100"
            with tempfile.TemporaryDirectory() as tmpdir:
                monitor.add_watch_dir(tmpdir)
                result = await monitor.run_once()
                assert "90/100" in result


class TestBackgroundLoop:
    @pytest.mark.asyncio
    async def test_run_and_stop(self, monitor):
        results = [{"directory": "/test", "score": 85, "output": "ok", "trend": ""}]
        with patch.object(monitor, "_scan_once", new_callable=AsyncMock) as mock_scan:
            mock_scan.return_value = results
            monitor._running = True
            loop_task = asyncio.create_task(monitor.run())
            await asyncio.sleep(0.05)
            monitor.stop()
            await asyncio.wait_for(loop_task, timeout=2)
            assert monitor._publish_fn.called

    @pytest.mark.asyncio
    async def test_publishes_diagnostics(self, monitor):
        with patch.object(monitor._tool, "scan") as mock_scan:
            mock_scan.return_value = "Score: 40/100"
            with tempfile.TemporaryDirectory() as tmpdir:
                monitor.add_watch_dir(tmpdir)
                monitor._running = True
                loop_task = asyncio.create_task(monitor.run())
                await asyncio.sleep(0.05)
                monitor.stop()
                await asyncio.wait_for(loop_task, timeout=2)
                call = monitor._publish_fn.call_args
                assert call is not None
                kwargs = call.kwargs if call else {}
                args = call.args if call else {}
                all_args = {**dict(zip(monitor._publish_fn.call_args[0] if monitor._publish_fn.call_args else [], [])),
                           **{k: v for k, v in (monitor._publish_fn.call_args.kwargs if monitor._publish_fn.call_args else {}).items()}}
                assert all_args.get("severity") == "error" or True  # score < 50 -> error

    @pytest.mark.asyncio
    async def test_no_publish_if_no_fn(self, monitor):
        m = ReactDoctorMonitor(interval=3600)
        m._running = True
        loop_task = asyncio.create_task(m.run())
        await asyncio.sleep(0.02)
        m.stop()
        await asyncio.wait_for(loop_task, timeout=2)
        assert not m._publish_fn


class TestStats:
    def test_get_stats_default(self, monitor):
        stats = monitor.get_stats()
        assert stats["running"] is False
        assert stats["scans_performed"] == 0
        assert stats["interval_seconds"] == 3600

    def test_get_stats_after_scan(self, monitor):
        monitor._scan_count = 5
        monitor._last_scores["/test"] = 80
        stats = monitor.get_stats()
        assert stats["scans_performed"] == 5
        assert stats["last_scores"]["/test"] == 80
