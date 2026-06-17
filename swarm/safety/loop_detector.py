from collections import defaultdict


class LoopDetector:
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._handoff_history: list[tuple[str, str]] = []
        self._pair_counts: dict[tuple[str, str], int] = defaultdict(int)

    def record_handoff(self, from_agent: str, to_agent: str):
        self._handoff_history.append((from_agent, to_agent))
        self._pair_counts[(from_agent, to_agent)] += 1

    def is_looping(self) -> bool:
        if len(self._handoff_history) < self.threshold:
            return False
        recent = self._handoff_history[-self.threshold:]
        if len(set(recent)) == 1:
            return True
        for pair, count in self._pair_counts.items():
            if count >= self.threshold:
                first_idx = next(
                    i for i, h in enumerate(self._handoff_history) if h == pair
                )
                if self._handoff_history[-1] == pair:
                    return True
        return False

    def detect_cycle(self) -> list:
        if len(self._handoff_history) < 4:
            return []
        recent = self._handoff_history[-6:]
        for length in range(2, len(recent) // 2 + 1):
            for start in range(len(recent) - length * 2 + 1):
                pattern = recent[start : start + length]
                if recent[start + length : start + length * 2] == pattern:
                    return pattern
        return []

    def summary(self) -> str:
        if not self._handoff_history:
            return "No handoffs yet"
        return " -> ".join(f"{a}->{b}" for a, b in self._handoff_history[-10:])
