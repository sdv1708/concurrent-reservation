"""
Phase 11 — Booking tests.

Inventory rows start today, so every stay in these tests uses dates
relative to `date.today()`. Stripe calls are always mocked.
"""
import uuid
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


def test_init_booking_returns_409_when_stay_unavailable(client, guest_headers, active_hotel):
    """The room type has 5 rooms. A hold on 6 rooms is a conflict."""
    r = client.post("/bookings/init", headers=guest_headers, json={
        "hotel_id": active_hotel["hotel"]["id"],
        "room_id": active_hotel["room"]["id"],
        "check_in_date": _days_from_today(10),
        "check_out_date": _days_from_today(12),
        "rooms_count": 6
    })
    assert r.status_code == 409


def _book_counts(client, manager_headers, room_id) -> dict[str, int]:
    rows = client.get(f"/admin/inventory/rooms/{room_id}", headers=manager_headers).json()
    return {row["date"]: row["book_count"] for row in rows}


@patch("app.routers.webhooks.stripe.Webhook.construct_event")
@patch("app.services.booking_service.stripe.checkout.Session.create")
def test_repeated_confirm_does_not_book_twice(
    mock_create, mock_event, client, guest_headers, manager_headers, active_hotel
):
    """A repeated Stripe webhook for the same session adds booked rooms once only."""
    room_id = active_hotel["room"]["id"]
    session_id = f"sess_{uuid.uuid4().hex}"
    mock_create.return_value = MagicMock(id=session_id, url="https://stripe.test.com/pay")
    mock_event.return_value = {
        "type": "checkout.session.completed",
        "data": {"object": {"id": session_id}},
    }

    init_resp = client.post("/bookings/init", headers=guest_headers, json={
        "hotel_id": active_hotel["hotel"]["id"],
        "room_id": room_id,
        "check_in_date": _days_from_today(40),
        "check_out_date": _days_from_today(42),
        "rooms_count": 2
    })
    assert init_resp.status_code == 201
    booking_id = init_resp.json()["id"]
    assert client.post(f"/bookings/{booking_id}/payments", headers=guest_headers).status_code == 200

    for _ in range(2):
        r = client.post("/webhook/payment", headers={"Stripe-Signature": "t=1,v1=x"}, content=b"{}")
        assert r.status_code == 204

    counts = _book_counts(client, manager_headers, room_id)
    assert counts[_days_from_today(40)] == 2
    assert counts[_days_from_today(41)] == 2
    assert counts[_days_from_today(42)] == 0  # the check-out date is not a night
    status = client.get(f"/bookings/{booking_id}/status", headers=guest_headers).json()
    assert status["booking_status"] == "CONFIRMED"
