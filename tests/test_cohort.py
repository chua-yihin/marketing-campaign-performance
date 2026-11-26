import pandas as pd

from campaign_perf.cohort import flag_internal

USERS = pd.DataFrame(
    {
        "channel": ["Referral", "Referral", "Organic", "Social", "Referral"],
        "source": ["(direct)", "google.com", "(direct)", "facebook", "(direct)"],
        "medium": ["(none)", "referral", "(none)", "social", "referral"],
    }
)


def test_rule_requires_all_fields():
    rule = {"channel": "Referral", "source": "(direct)", "medium": "(none)"}
    assert list(flag_internal(USERS, [rule])) == [True, False, False, False, False]


def test_rules_ored():
    rules = [
        {"channel": "Referral", "source": "(direct)", "medium": "(none)"},
        {"channel": "Social"},
    ]
    assert list(flag_internal(USERS, rules)) == [True, False, False, True, False]


def test_no_rules():
    assert not flag_internal(USERS, []).any()
