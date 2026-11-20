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


def _search(client, headers, **body):
    return client.request("GET", "/hotels/search", headers=headers, json=body)


def test_search_lists_active_hotel_with_availability(client, manager_headers):
    from datetime import date, timedelta
    import uuid

    city = f"city-{uuid.uuid4().hex[:8]}"  # a city that no other test uses
    hotel = client.post("/admin/hotels", headers=manager_headers, json={
        "name": "Search Hotel", "city": city, "photos": [], "amenities": [],
    }).json()
    client.patch(f"/admin/hotels/{hotel['id']}/activate", headers=manager_headers)
    r = client.post(f"/admin/hotels/{hotel['id']}/rooms", headers=manager_headers, json={
        "type": "SUITE", "base_price": 90.00, "photos": [], "amenities": [],
        "total_count": 2, "capacity": 2,
    })
    assert r.status_code == 201

    start = (date.today() + timedelta(days=10)).isoformat()
    end = (date.today() + timedelta(days=12)).isoformat()
    r = _search(client, manager_headers, city=city, rooms_count=1, start_date=start, end_date=end)
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["page"], body["total_elements"], body["total_pages"]) == (1, 1, 1)
    assert [h["id"] for h in body["content"]] == [hotel["id"]]
    assert float(body["content"][0]["min_price"]) == 90.0

    r = _search(client, manager_headers, city=city, rooms_count=3, start_date=start, end_date=end)
    assert r.json()["total_elements"] == 0


def test_search_rejects_bad_stay_and_page(client, guest_headers):
    start = "2030-01-10"
    assert _search(client, guest_headers, city="x", rooms_count=1,
                   start_date=start, end_date=start).status_code == 422
    assert _search(client, guest_headers, city="x", rooms_count=1, page=0,
                   start_date=start, end_date="2030-01-12").status_code == 422
