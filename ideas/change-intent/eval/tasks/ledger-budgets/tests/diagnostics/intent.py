"""Intent artifact checks. Only meaningful for processes that author an intent. Weight 0 in the headline."""
from rewardkit import criteria

criteria.intent_file_present(weight=1.0)
criteria.intent_has_required_sections(weight=1.0)
criteria.author_approved(weight=1.0)
