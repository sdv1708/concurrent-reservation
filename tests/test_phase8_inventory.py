"""
Phase 8 — Inventory admin tests.

`active_hotel` fixture activates the hotel and creates one room, which
should trigger 365 inventory rows to be pre-generated.
"""
from datetime import date, timedelta


def test_list_inventory(client, manager_headers, active_hotel):
    room_id = active_hotel["room"]["id"]
    r = client.get(f"/admin/inventory/rooms/{room_id}", headers=manager_headers)
    assert r.status_code == 200
    assert len(r.json()) == 365


def test_bulk_update_closes_dates(client, manager_headers, active_hotel):
    room_id = active_hotel["room"]["id"]
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    r = client.patch(f"/admin/inventory/rooms/{room_id}", headers=manager_headers, json={
        "start_date": today,
        "end_date": tomorrow,
        "closed": True
    })
    assert r.status_code == 200
    assert all(row["closed"] for row in r.json())
