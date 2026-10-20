"""Hidden acceptance tests: the primary, objective measure."""
from rewardkit import criteria

criteria.hidden_tests_pass_fraction(weight=3.0)
criteria.hidden_tests_all_pass(weight=1.0)
