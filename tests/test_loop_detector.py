from swarm.safety.loop_detector import LoopDetector


def test_no_loop():
    detector = LoopDetector(threshold=3)
    detector.record_handoff("a", "b")
    detector.record_handoff("b", "c")
    assert not detector.is_looping()


def test_simple_loop():
    detector = LoopDetector(threshold=3)
    for _ in range(3):
        detector.record_handoff("a", "b")
        detector.record_handoff("b", "a")
    assert detector.is_looping()


def test_below_threshold():
    detector = LoopDetector(threshold=4)
    for _ in range(2):
        detector.record_handoff("x", "y")
    assert not detector.is_looping()


def test_cycle_detection():
    detector = LoopDetector()
    for _ in range(3):
        detector.record_handoff("a", "b")
        detector.record_handoff("b", "c")
        detector.record_handoff("c", "a")
    cycle = detector.detect_cycle()
    assert len(cycle) >= 2


def test_summary():
    detector = LoopDetector()
    assert "No handoffs" in detector.summary()
    detector.record_handoff("a", "b")
    assert "a->b" in detector.summary()
