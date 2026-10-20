"""Fixed reviewer verdict (eval/reviewer/): identical reviewer for every process version."""
from rewardkit import criteria

criteria.fixed_review_present(weight=1.0)
criteria.reviewer_verdict_correct(weight=2.0)
criteria.no_blocking_findings(weight=2.0)
