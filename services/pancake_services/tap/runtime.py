"""TAP runtime: scheduler + executor.

The runtime owns retry policy (adapters stay dumb): a task that raises or
returns None is retried with exponential backoff up to ``max_retries``,
then recorded as failed for this run and picked up again on the next tick.

The ingest interface -- FROZEN for adapter authors:
    sink(bite: dict) -> None
Any callable accepting one BITE envelope works; the production sink is
``BiteStore.save`` (pancake_services.store.bites). This is the interface
contract vendor-adapter workstreams code against.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from pancake_services.tap.adapter_base import SIRUPType, TAPAdapter, TAPAdapterFactory

logger = logging.getLogger(__name__)

BiteSink = Callable[[Dict[str, Any]], None]


@dataclass
class TaskSpec:
    """One scheduled fetch: a (geoid, sirup_type, params) triple for a vendor."""

    geoid: str
    sirup_type: SIRUPType
    params: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VendorSchedule:
    vendor_name: str
    interval_seconds: int
    tasks: List[TaskSpec]


@dataclass
class TaskResult:
    vendor: str
    geoid: str
    sirup_type: str
    ok: bool
    attempts: int
    error: Optional[str] = None


@dataclass
class RunReport:
    vendor: str
    results: List[TaskResult] = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for r in self.results if r.ok)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.ok)


def schedule_from_config(vendor_config: Dict[str, Any]) -> Optional[VendorSchedule]:
    schedule = vendor_config.get("schedule")
    if not schedule:
        return None
    tasks = [
        TaskSpec(
            geoid=t["geoid"],
            sirup_type=SIRUPType(t["sirup_type"]),
            params=t.get("params", {}),
        )
        for t in schedule.get("tasks", [])
    ]
    return VendorSchedule(
        vendor_name=vendor_config["vendor_name"],
        interval_seconds=int(schedule.get("interval_seconds", 3600)),
        tasks=tasks,
    )


class TAPRuntime:
    def __init__(
        self,
        factory: TAPAdapterFactory,
        sink: BiteSink,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.factory = factory
        self.sink = sink
        self.max_retries = max_retries
        self.backoff_base = backoff_base_seconds
        self._sleep = sleep
        self._stop = threading.Event()

    # -- executor -----------------------------------------------------------

    def _execute_task(self, adapter: TAPAdapter, task: TaskSpec) -> TaskResult:
        last_error: Optional[str] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                bite = adapter.fetch_and_transform(task.geoid, task.sirup_type, task.params)
            except Exception as e:  # noqa: BLE001 - vendor code is untrusted
                bite = None
                last_error = f"{type(e).__name__}: {e}"
                logger.warning(
                    "TAP task failed (vendor=%s geoid=%s attempt=%d): %s",
                    adapter.vendor_name, task.geoid, attempt, last_error,
                )
            if bite is not None:
                self.sink(bite)
                return TaskResult(
                    vendor=adapter.vendor_name,
                    geoid=task.geoid,
                    sirup_type=task.sirup_type.value,
                    ok=True,
                    attempts=attempt,
                )
            if last_error is None:
                last_error = "adapter returned None"
            if attempt < self.max_retries:
                self._sleep(self.backoff_base * (2 ** (attempt - 1)))
        return TaskResult(
            vendor=adapter.vendor_name,
            geoid=task.geoid,
            sirup_type=task.sirup_type.value,
            ok=False,
            attempts=self.max_retries,
            error=last_error,
        )

    def run_once(self, schedule: VendorSchedule) -> RunReport:
        """Execute all of one vendor's scheduled tasks once."""
        report = RunReport(vendor=schedule.vendor_name)
        adapter = self.factory.get_adapter(schedule.vendor_name)
        if adapter is None:
            logger.error("no adapter registered for vendor %s", schedule.vendor_name)
            for task in schedule.tasks:
                report.results.append(TaskResult(
                    vendor=schedule.vendor_name, geoid=task.geoid,
                    sirup_type=task.sirup_type.value, ok=False, attempts=0,
                    error="adapter not registered",
                ))
            return report
        for task in schedule.tasks:
            report.results.append(self._execute_task(adapter, task))
        logger.info(
            "TAP run complete (vendor=%s ok=%d failed=%d)",
            schedule.vendor_name, report.succeeded, report.failed,
        )
        return report

    # -- scheduler ----------------------------------------------------------

    def run_forever(self, schedules: List[VendorSchedule]) -> None:
        """Simple interval scheduler; one thread per vendor."""
        threads = []
        for schedule in schedules:
            thread = threading.Thread(
                target=self._vendor_loop, args=(schedule,), daemon=True,
                name=f"tap-{schedule.vendor_name}",
            )
            thread.start()
            threads.append(thread)
        for thread in threads:
            thread.join()

    def _vendor_loop(self, schedule: VendorSchedule) -> None:
        while not self._stop.is_set():
            self.run_once(schedule)
            self._stop.wait(schedule.interval_seconds)

    def stop(self) -> None:
        self._stop.set()
