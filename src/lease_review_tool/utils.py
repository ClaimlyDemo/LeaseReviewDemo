from __future__ import annotations

import math
from statistics import mean, median
from typing import Iterable


def _as_float_list(values: Iterable[float] | None) -> list[float]:
    if values is None:
        return []
    return [float(value) for value in values]


def cosine_similarity(left: Iterable[float] | None, right: Iterable[float] | None) -> float:
    left_values = _as_float_list(left)
    right_values = _as_float_list(right)

    if len(left_values) == 0 or len(right_values) == 0:
        return 0.0

    numerator = sum(a * b for a, b in zip(left_values, right_values))
    left_norm = math.sqrt(sum(a * a for a in left_values))
    right_norm = math.sqrt(sum(b * b for b in right_values))
    denominator = left_norm * right_norm
    if denominator == 0:
        return 0.0
    return numerator / denominator


def summarize_numeric_values(values: list[float]) -> dict[str, float]:
    return {
        "min": min(values),
        "max": max(values),
        "mean": mean(values),
        "median": median(values),
    }
