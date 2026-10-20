"""Intent artifact checks. Only meaningful for processes that author an intent; the baseline scores 0 here, which is expected and is why `process` carries low weight in the overall reward."""
from rewardkit import criteria

criteria.intent_file_present(weight=1.0)
criteria.intent_has_required_sections(weight=1.0)
