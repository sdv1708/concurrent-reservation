"""
Phase 11 — Booking tests.

`with_for_update()` is not supported by SQLite, so we patch it on the
SQLAlchemy Select object so it becomes a no-op in the test environment.
Stripe calls are always mocked.
"""
from unittest.mock import patch, MagicMock


# ── Helper: patch SELECT FOR UPDATE to be a no-op for SQLite ─────────────────
# Patching an unbound method — side_effect receives (self, **kw) where self
# is the actual Select instance. Returning `self` keeps the query chain intact.
_FOR_UPDATE_PATCH = "sqlalchemy.sql.selectable.Select.with_for_update"


def test_init_booking(client, guest_headers, active_hotel):
    """Reserve inventory for a future date range — no payment yet."""
    hotel_id = active_hotel["hotel"]["id"]
    room_id = active_hotel["room"]["id"]

    with patch(_FOR_UPDATE_PATCH, lambda self, **kw: self):
        r = client.post("/bookings/init", headers=guest_headers, json={
            "hotel_id": hotel_id,
            "room_id": room_id,
            "check_in_date": "2026-08-05",
            "check_out_date": "2026-08-07",
            "rooms_count": 1
        })
    assert r.status_code == 201
    assert r.json()["booking_status"] == "RESERVED"


@patch("app.services.booking_service.stripe.checkout.Session.create")
def test_initiate_payment(mock_create, client, guest_headers, active_hotel):
    """After init, calling /bookings/{id}/pay creates a Stripe session."""
    hotel_id = active_hotel["hotel"]["id"]
    room_id = active_hotel["room"]["id"]

    mock_create.return_value = MagicMock(id="sess_test_123", url="https://stripe.test.com/pay")

    # First init a booking
    with patch(_FOR_UPDATE_PATCH, lambda self, **kw: self):
        init_resp = client.post("/bookings/init", headers=guest_headers, json={
            "hotel_id": hotel_id,
            "room_id": room_id,
            "check_in_date": "2026-09-01",
            "check_out_date": "2026-09-03",
            "rooms_count": 1
        })
    assert init_resp.status_code == 201
    booking_id = init_resp.json()["id"]

    # Then initiate payment
    pay_resp = client.post(f"/bookings/{booking_id}/payments", headers=guest_headers)
    assert pay_resp.status_code == 200
    assert "payment_url" in pay_resp.json()
