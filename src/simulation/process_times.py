"""Synthetic timing inputs with unit/station keyed reproducible random draws."""

import hashlib
import math
import random


def validate_timing(config):
    timing = config.get("processing_time", {"distribution": "fixed"})
    if not isinstance(timing, dict) or timing.get("distribution") not in (
        "fixed",
        "triangular",
    ):
        raise ValueError("processing_time distribution must be fixed or triangular")
    if timing["distribution"] == "triangular":
        width = timing.get("relative_half_width")
        if (
            isinstance(width, bool)
            or not isinstance(width, (int, float))
            or not math.isfinite(width)
            or not 0 <= width < 1
        ):
            raise ValueError(
                "relative_half_width must be finite and between 0 inclusive and 1 exclusive"
            )
        if type(config.get("seed")) is not int:
            raise ValueError("Triangular timing requires an integer seed")
    return timing


def sample_duration(config, timing, station, unit_id):
    mean = station["mean_process_s"]
    if timing["distribution"] == "fixed":
        return mean
    width = timing["relative_half_width"]
    if width == 0:
        return mean
    # No dependence on event ordering or shared mutable RNG state. The same
    # unit/station draw is reused across paired staffing/variation scenarios.
    key = f"process|{config['seed']}|{station['id']}|{unit_id}|1".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest(), "big")
    return random.Random(seed).triangular(mean * (1 - width), mean * (1 + width), mean)
