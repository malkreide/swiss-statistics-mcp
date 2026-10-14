"""Call a tool the way the timeout hint tells a client to.

Live runs of 21.9., 28.9. and 12.10.2026 went red on `test_live_population_
zurich`, each time with «Zeitüberschreitung: BFS STAT-TAB …». The contract
with the source held every time: on 14.10. the very query took 36.1s cold and
1.0s on the next call, value unchanged; in the live suite an hour later it took
more than 52s. Cold STAT-TAB queries run past any budget a 30s client allows,
so a single call measures the source's cache, not its contract.

The server's answer is twofold: the query keeps running when the caller's
budget is spent (`DETACHED_BUDGET` in server.py), and the hint says «Ein
erneuter Aufruf kann gelingen». This helper follows the hint, and each repeat
joins the query already running instead of starting a new one. That keeps the
live suite testing what a client relies on — the data shape, and that coming
back works — without widening the budget the suite exercises.

The repeats are bounded: together they cover `DETACHED_BUDGET`, after which
the server itself has given up and a further call would start from scratch. A
timeout at that point is a real finding. Any other error is returned at once,
untouched, and fails the test as before. A repeat is reported with
`warnings.warn`, so the log shows how often the source was cold even when the
suite is green — the latency is observed, the contract is asserted.
"""

from __future__ import annotations

import asyncio
import math
import time
import warnings
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel

import swiss_statistics_mcp.server as srv

TIMEOUT_PREFIX = "Zeitüberschreitung"

# A repeat that comes early does not fail, it waits for the same computation —
# so the pause only has to be short, not exact.
REPEAT_PAUSE = 2.0

# A module alias, so a test can replace the pause without touching `asyncio`
# itself — patching `asyncio.sleep` would disarm it for the whole process.
_sleep = asyncio.sleep


def max_calls() -> int:
    """First call plus enough repeats to outlast the detached query."""
    return 1 + math.ceil(srv.DETACHED_BUDGET / srv.RETRY_TOTAL_BUDGET)


async def call_as_client(call: Callable[[], Awaitable[BaseModel]]) -> dict[str, Any]:
    """`call()`'s result as a dict, repeated while it times out (bounded)."""
    t0 = time.monotonic()
    limit = max_calls()
    for n in range(1, limit + 1):
        data = (await call()).model_dump(exclude_none=True)
        if not str(data.get("error", "")).startswith(TIMEOUT_PREFIX) or n == limit:
            break
        await _sleep(REPEAT_PAUSE)
    if n > 1:
        warnings.warn(
            f"Quelle kalt: {n} Aufrufe in {time.monotonic() - t0:.0f} s"
            f" ({'Daten' if 'error' not in data else data['error']})",
            stacklevel=2,
        )
    return data
