"""Did the process's own stages (author, review) finish cleanly? Diagnostic; the headline only counts the shared stages."""
from rewardkit import criteria

criteria.process_stages_clean(weight=1.0)
