"""Condition-invariant hygiene: every process can satisfy these identically."""
from rewardkit import criteria

criteria.implementation_committed(weight=1.0)
criteria.summary_recorded(weight=1.0)
