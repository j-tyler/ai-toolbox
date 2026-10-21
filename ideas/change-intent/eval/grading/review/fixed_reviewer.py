"""Fixed reviewer verdict (eval/reviewer/): identical reviewer, custom instructions off, same inputs for every condition."""
from rewardkit import criteria

criteria.fixed_review_present(weight=1.0)
criteria.reviewer_verdict_correct(weight=2.0)
criteria.no_blocking_findings(weight=2.0)
