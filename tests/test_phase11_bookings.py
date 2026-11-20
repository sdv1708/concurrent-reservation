"""
Phase 11 — Booking tests.

Inventory rows start today, so every stay in these tests uses dates
relative to `date.today()`. Stripe calls are always mocked.
"""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock


def _days_from_today(n: int) -> str:
    return (date.today() + timedelta(days=n)).isoformat()


def test_init_booking(client, guest_headers, active_hotel):
    """Place a hold for a future stay. No payment yet."""
    hotel_id = active_hotel["hotel"]["id"]
    room_id = active_hotel["room"]["id"]

    r = client.post("/bookings/init", headers=guest_headers, json={
        "hotel_id": hotel_id,
        "room_id": room_id,
        "check_in_date": _days_from_today(10),
        "check_out_date": _days_from_today(12),
        "rooms_count": 1
    })
    assert r.status_code == 201
    assert r.json()["booking_status"] == "RESERVED"


@patch("app.services.booking_service.stripe.checkout.Session.create")
def test_initiate_payment(mock_create, client, guest_headers, active_hotel):
    """After init, calling /bookings/{id}/payments creates a Stripe session."""
    hotel_id = active_hotel["hotel"]["id"]
    room_id = active_hotel["room"]["id"]

    mock_create.return_value = MagicMock(id="sess_test_123", url="https://stripe.test.com/pay")

    # First init a booking
    init_resp = client.post("/bookings/init", headers=guest_headers, json={
        "hotel_id": hotel_id,
        "room_id": room_id,
        "check_in_date": _days_from_today(30),
        "check_out_date": _days_from_today(32),
        "rooms_count": 1
    })
    assert init_resp.status_code == 201
    booking_id = init_resp.json()["id"]

    # Then initiate payment
    pay_resp = client.post(f"/bookings/{booking_id}/payments", headers=guest_headers)
    assert pay_resp.status_code == 200
    assert "payment_url" in pay_resp.json()
