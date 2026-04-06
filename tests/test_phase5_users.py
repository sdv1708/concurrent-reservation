"""
Phase 5 — User profile and guest management tests.
"""


def test_get_profile(client, guest_headers):
    r = client.get("/users/profile", headers=guest_headers)
    assert r.status_code == 200
    assert "email" in r.json()


def test_update_profile(client, guest_headers):
    r = client.patch("/users/profile", headers=guest_headers, json={"name": "Updated Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_guest_crud(client, guest_headers):
    # Create
    r = client.post("/users/guests", headers=guest_headers, json={
        "name": "Alice", "gender": "FEMALE", "age": 30
    })
    assert r.status_code == 201
    gid = r.json()["id"]

    # List
    r = client.get("/users/guests", headers=guest_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Update
    r = client.put(f"/users/guests/{gid}", headers=guest_headers, json={
        "name": "Alice Updated", "gender": "FEMALE", "age": 31
    })
    assert r.status_code == 200

    # Delete
    r = client.delete(f"/users/guests/{gid}", headers=guest_headers)
    assert r.status_code == 204
