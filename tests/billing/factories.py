import uuid

from app.billing.models import Plan, Subscription


def make_plan(**kwargs) -> Plan:
    """Return an unsaved Plan with sensible defaults."""
    import random
    defaults = {
        "id": random.randint(10_000, 99_999),
        "name": "test_basic",
        "price_monthly": 29.00,
        "max_properties": 1,
        "max_rooms": 10,
        "online_payments": False,
        "auto_confirm": False,
        "promotions_enabled": False,
        "stripe_price_id": "price_test_basic",
    }
    defaults.update(kwargs)
    return Plan(**defaults)


def make_subscription(user_id: uuid.UUID, plan_id: int = 999, **kwargs) -> Subscription:
    """Return an unsaved Subscription with sensible defaults."""
    defaults = {
        "user_id": user_id,
        "plan_id": plan_id,
        "stripe_subscription_id": f"sub_test_{uuid.uuid4().hex[:12]}",
        "stripe_customer_id": f"cus_test_{uuid.uuid4().hex[:12]}",
        "status": "active",
        "current_period_end": None,
    }
    defaults.update(kwargs)
    return Subscription(**defaults)
