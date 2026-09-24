from txtlocal.entrypoints import wiring


def test_billing_sends_stripe_checkout_back_to_the_public_site() -> None:
    assert wiring.billing().public_base_url == wiring.settings().public_base_url


def test_billing_can_queue_an_automatic_recharge() -> None:
    assert wiring.billing().bus is wiring.bus()
