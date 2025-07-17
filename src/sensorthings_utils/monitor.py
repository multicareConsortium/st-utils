"""Background monitor for program performance."""

# standard
from datetime import datetime
import time
import logging
import threading
from collections import defaultdict
from typing import Mapping

logger = logging.getLogger("network_monitor")


class NetworkMonitor:
    """Monitor connections and uploads."""

    def __init__(self):
        self.start_time = datetime.now()
        self.starting_application_threads: set[str] = set()
        self.push_success: dict[str, int] = defaultdict(int)
        self.push_fail: dict[str, int] = defaultdict(int)
        self.last_push_time: dict[str, float] = defaultdict(float)
        self.rejected_payloads: dict[str, int] = defaultdict(int)
        self.sensor_config_fail: int = 0
        self.payloads_received: dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def set_starting_threads(self, starting_threads: list[str] | set[str]):
        if not starting_threads:
            raise ValueError("No threads passed.")
        self.starting_application_threads = set(starting_threads)

    @property
    def live_threads(self):
        return set([i.name for i in threading.enumerate()])

    def add_count(self, attr: str, count: int = 1):
        with self._lock:
            v = self.__getattribute__(attr) + count
            self.__setattr__(attr, v)
        return None

    def reduce_count(self, attr: str, count: int = 1):
        with self._lock:
            v = self.__getattribute__(attr) - count
            self.__setattr__(attr, v)
        return None

    def add_named_time(self, attr: str, application: str, time: float):
        with self._lock:
            self.__getattribute__(attr)[application] = time

    def add_named_count(self, attr: str, application: str, count: int = 1):
        """For counts associated with named applications."""

        with self._lock:
            self.__getattribute__(attr)[application] += count

    def report(self, interval: int = 30):
        time.sleep(60 * interval)
        with self._lock:
            # Report on active threads.
            dead_threads = self.starting_application_threads - self.live_threads
            thread_line = (
                f"All original threads alive: {self.starting_application_threads}."
                if not dead_threads
                else f"Some threads have died: {dead_threads}."
            )
            logger.info(
                f"Periodic Health Report {"-"*(len(thread_line)-len("Period Health Report"))}"
            )
            if not dead_threads:
                logger.info(thread_line)
            else:
                logger.warning(thread_line)
            # Report succesful pushes:
            logger.info(f"Uptime: {datetime.now()-self.start_time}")
            if self.sensor_config_fail > 0:
                logger.warning(
                    f"{self.sensor_config_fail} sensor configuration file/s are invalid!"
                )
            for k, v in self.payloads_received.items():
                logger.info(f"Payloads received from {k} → {v}")
            for k, v in self.rejected_payloads.items():
                logger.warning(f"Payloads rejected for {k} → {v}")
            for k, v in self.push_success.items():
                time_since_last_push = (time.time() - self.last_push_time[k]) / 60
                logger.info(
                    f"Observations created for {k} → {v} (Time since last push: {time_since_last_push:.2f}m)."
                )
            for k, v in self.push_fail.items():
                logger.warning(f"Rejected observations for {k} → {v}")
            for k, v in self.last_push_time.items():
                if v - time.time() > 3600:
                    logger.warning(
                        f"Have not received observations from {k} in {v:.2f}."
                    )
            logger.info("Check logs for full details.")


network_monitor = NetworkMonitor()
