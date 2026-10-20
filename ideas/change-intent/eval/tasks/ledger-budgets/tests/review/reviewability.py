"""How reviewable the change is, as rated by the fixed reviewer given the process's own change description."""
from rewardkit import criteria

criteria.reviewability_score(weight=3.0)
criteria.description_adequacy(weight=1.0)
criteria.review_effort_low(weight=1.0)
criteria.few_unverifiable_claims(weight=1.0)
