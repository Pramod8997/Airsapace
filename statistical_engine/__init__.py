"""AirStat India statistical engine.

Pure, deterministic functions only. The official index calculation NEVER uses an
LLM, opaque model or unversioned heuristic (core architectural invariant). Same input
snapshot + methodology version + weights must produce the same result.
"""
