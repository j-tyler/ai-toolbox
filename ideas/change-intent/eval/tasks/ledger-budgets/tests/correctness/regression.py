"""Existing behaviour, the agent's own suite, and the stdlib constraint."""
from rewardkit import criteria

criteria.existing_tests_still_pass(weight=2.0)
criteria.agent_tests_pass(weight=1.0)
criteria.stdlib_only(weight=1.0)
