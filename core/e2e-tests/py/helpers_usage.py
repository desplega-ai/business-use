"""
Uses act() and assert_() helpers instead of ensure().
Scanner should detect all 3 and infer types from function name.
"""
from business_use import act, assert_


act(
    id="user_signup",
    flow="onboarding",
    run_id="run_001",
    data={"email": "user@example.com"},
)

act(
    id="email_verified",
    flow="onboarding",
    run_id="run_001",
    data={"verified": True},
    dep_ids=["user_signup"],
)

assert_(
    id="profile_complete",
    flow="onboarding",
    run_id="run_001",
    data={"has_name": True, "has_avatar": True},
    dep_ids=["user_signup", "email_verified"],
    validator=lambda data, ctx: data["has_name"] and data["has_avatar"],
    description="User profile is complete after onboarding",
)
