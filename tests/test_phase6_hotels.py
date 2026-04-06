"""
Phase 6 — Hotel admin tests (create, activate, delete).
"""


def test_create_hotel(client, manager_headers):
    r = client.post("/admin/hotels", headers=manager_headers, json={
        "name": "New Hotel",
        "city": "Dallas",
        "photos": [],
        "amenities": [],
        "contact_phone": "5559876543",
        "contact_email": "dallas@test.com",
        "contact_address": "456 Elm St",
        "contact_location": "32.7767,-96.7970"
    })
    assert r.status_code == 201
    assert r.json()["active"] is False   # always starts inactive


def test_activate_hotel(client, manager_headers, test_hotel):
    r = client.patch(f"/admin/hotels/{test_hotel['id']}/activate", headers=manager_headers)
    assert r.status_code == 200
    assert r.json()["active"] is True


def test_delete_hotel(client, manager_headers, test_hotel):
    r = client.delete(f"/admin/hotels/{test_hotel['id']}", headers=manager_headers)
    assert r.status_code == 204
