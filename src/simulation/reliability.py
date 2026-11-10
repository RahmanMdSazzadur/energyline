"""Synthetic processing-time failure clocks and repair durations."""

import hashlib
import math
import random


def validate_reliability(config):
    enabled = False
    for station in config["stations"]:
        settings = station.get("reliability")
        if settings is None:
            continue
        enabled = True
        if not isinstance(settings, dict):
            raise ValueError("reliability must be an object")
        for key in ("mtbf_s", "repair_mean_s"):
            value = settings.get(key)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
                or value <= 0
            ):
                raise ValueError(f"{key} must be finite and positive")
        for key in ("uptime_distribution", "repair_distribution"):
            if settings.get(key, "exponential") not in ("fixed", "exponential"):
                raise ValueError(
                    "Reliability distributions must be fixed or exponential"
                )
    if enabled and type(config.get("seed")) is not int:
        raise ValueError("Reliability requires an integer seed")
    return enabled


def draw(config, station, cycle, kind):
    settings = station.get("reliability")
    if settings is None:
        return math.inf
    mean = settings["mtbf_s" if kind == "uptime" else "repair_mean_s"]
    distribution = settings.get(f"{kind}_distribution", "exponential")
    if distribution == "fixed":
        return mean
    key = f"reliability|{kind}|{config['seed']}|{station['id']}|{cycle}".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest(), "big")
    return max(random.Random(seed).expovariate(1 / mean), 1e-9)
