"""The process's own review pass. Absent for processes without one. Weight 0 in the headline."""
from rewardkit import criteria

criteria.process_review_present(weight=1.0)
criteria.process_review_assessed_claims(weight=1.0)
criteria.process_review_determinacy(weight=1.0)
