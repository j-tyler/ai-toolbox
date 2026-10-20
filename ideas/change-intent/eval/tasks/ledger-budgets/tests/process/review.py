"""The process's own review pass (change-intent review guidance). Processes without a review stage score 0 here by design."""
from rewardkit import criteria

criteria.process_review_present(weight=1.0)
criteria.process_review_assessed_claims(weight=1.0)
criteria.process_review_determinacy(weight=1.0)
