"""Deterministic severity update function.
Does NOT rely on Gemini — pure math based on time_down_s, stillness, motion."""

from __future__ import annotations


def compute_severity(
    severity_seed: int,
    time_down_s: float,
    stillness_score: float,
    motion_energy: float,
    acknowledged: bool,
) -> int:
    """Deterministic severity calculation.
    severity_current starts at severity_seed.
    Increases with time down and stillness.
    Decreases if motion resumes (recovery signal).
    Clamp between 1 and 5."""

    sev = severity_seed

    if time_down_s > 120:
        sev = max(sev, 5)
    elif time_down_s > 45:
        sev = max(sev, 4)
    elif time_down_s > 15:
        sev = max(sev, 3)

    if stillness_score > 0.9 and time_down_s > 30:
        sev = min(sev + 1, 5)

    if motion_energy > 0.5 and stillness_score < 0.3:
        sev = max(sev - 1, 1)

    if acknowledged:
        sev = max(sev - 1, 1)

    return max(1, min(5, sev))


def compute_risk_score(
    bed_state: str,
    stability: str,
    hour_of_day: int,
    base_score: float = 0.0,
) -> float:
    """Deterministic risk score for prevention mode."""
    score = base_score

    bed_state_scores = {
        "IN_BED": 0.0,
        "NEAR_EDGE": 0.2,
        "SITTING_EDGE": 0.4,
        "LEGS_OVER": 0.6,
        "STANDING_NEAR_BED": 0.3,
        "OUT_OF_BED": 0.1,
        "UNKNOWN": 0.15,
    }
    score += bed_state_scores.get(bed_state, 0.1)

    if stability == "UNSTABLE":
        score += 0.25
    elif stability == "UNKNOWN":
        score += 0.1

    if 22 <= hour_of_day or hour_of_day <= 5:
        score += 0.1

    return max(0.0, min(1.0, score))
