"""Synthetic perfect inspection and one-attempt offline rework inputs."""

import hashlib
import math
import random


def probability(value):
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(value)
        and 0 <= value <= 1
    )


def validate_quality(config):
    settings = config.get("quality")
    if settings is None:
        return None
    if not isinstance(settings, dict):
        raise ValueError("quality must be an object")
    ids = [s["id"] for s in config["stations"]]
    inspection = settings.get("inspection_station")
    if inspection not in ids or ids.index(inspection) != len(ids) - 2:
        raise ValueError(
            "Inspection must be at the penultimate station; final station labels/releases"
        )
    defects = settings.get("defect_probabilities", {})
    if not isinstance(defects, dict) or any(
        s not in ids[:-1] or not probability(p) for s, p in defects.items()
    ):
        raise ValueError(
            "Defect probabilities must be valid probabilities at or before inspection"
        )
    rework = settings.get("rework")
    if rework is not None:
        if not isinstance(rework, dict):
            raise ValueError("rework must be an object or null")
        duration = rework.get("duration_s")
        if (
            isinstance(duration, bool)
            or not isinstance(duration, (int, float))
            or not math.isfinite(duration)
            or duration <= 0
        ):
            raise ValueError("Rework duration must be finite and positive")
        if not probability(rework.get("success_probability")):
            raise ValueError("Invalid rework success probability")
    if type(config.get("seed")) is not int:
        raise ValueError("Quality requires an integer seed")
    return settings


def outcome(config, unit, kind, source, p):
    key = f"quality|{config['seed']}|{unit}|{kind}|{source}".encode()
    seed = int.from_bytes(hashlib.sha256(key).digest(), "big")
    return random.Random(seed).random() < p
