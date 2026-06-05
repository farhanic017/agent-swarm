#  Auto Model Switcher  ───  Performance Profiler
#  Copyright (c) 2026 Farhan Dhrubo  <farhaiee123@gmail.com>
#  License: GPL-3.0  —  https://github.com/farhanic017/auto-model-switcher
#
#  This program is free software. You may NOT remove this notice,
#  re-distribute as your own work, or sell without attribution.
# =============================================================================

"""Profile the auto-switcher to find bottlenecks."""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from switcher import (
    discover_providers, build_chain, check_all_parallel,
    _load_health_cache, _save_health_cache
)

t0 = time.time()
providers = discover_providers()
t1 = time.time()
print(f"Discover: {t1-t0:.2f}s ({len(providers)} models)")

# Group by provider type
from collections import Counter
provs = Counter(p["provider"] for p in providers)
for k, v in provs.most_common():
    print(f"  {k}: {v}")

t0 = time.time()
cache = _load_health_cache()
print(f"Cache loaded: {len(cache)} entries")

chain = build_chain(providers)
results = check_all_parallel(chain, cached_health=cache)
t1 = time.time()
print(f"Check: {t1-t0:.2f}s ({len(results)} results)")

healthy = sum(1 for v in results.values() if v[0])
print(f"Healthy: {healthy}/{len(results)}")

_save_health_cache(results)
print(f"Cache saved")
