"""Did the process run to completion and leave the artifacts it promises?"""
from rewardkit import criteria

criteria.implementation_committed(weight=1.0)
criteria.summary_recorded(weight=1.0)
criteria.agent_added_tests(weight=1.0)
