"""Full end-to-end workflow tests: submit -> pending -> review -> visible."""


CHAR_PAYLOAD = {
    "name": "Workflow Character",
    "originalName": "WorkflowCharOriginal",
    "type": "game",
    "officialImage": "https://example.com/char.png",
    "source": {"title": "Game", "company": "Studio", "releaseYear": 2024},
}

MAKER_PAYLOAD = {
    "name": "Workflow Maker",
    "originalName": "WorkflowMakerOriginal",
    "Avatar": "https://example.com/maker.png",
    "socialMedia": {"twitter": "https://twitter.com/maker"},
}

KIGER_PAYLOAD = {
    "name": "Workflow Kiger",
    "bio": "Workflow bio",
    "profileImage": "https://example.com/kiger.png",
    "position": "cosplayer",
    "isActive": True,
    "socialMedia": {"twitter": "https://twitter.com/kiger"},
    "Characters": [],
}


async def test_full_character_lifecycle(admin_client):
    # 1. Empty
    response = await admin_client.get("/characters")
    assert response.json() == []

    # 2. Submit
    submit = await admin_client.post("/character", json=CHAR_PAYLOAD)
    assert submit.status_code == 200
    pending_id = int(submit.json()["id"])

    # 3. See in pending
    pending = await admin_client.get("/admin/pending/characters")
    assert len(pending.json()) == 1

    # 4. Approve
    review = await admin_client.post(
        f"/admin/review/character/{pending_id}", json={"action": "approve"}
    )
    assert review.status_code == 200

    # 5. Visible in public API
    chars = await admin_client.get("/characters")
    data = chars.json()
    assert len(data) == 1
    assert data[0]["name"] == "Workflow Character"

    # 6. Get by ID
    char_id = data[0]["id"]
    detail = await admin_client.get(f"/character/{char_id}")
    assert detail.status_code == 200
    assert detail.json()["originalName"] == "WorkflowCharOriginal"


async def test_full_maker_lifecycle(admin_client):
    # Submit
    submit = await admin_client.post("/maker", json=MAKER_PAYLOAD)
    assert submit.status_code == 200
    pending_id = int(submit.json()["id"])

    # Approve
    review = await admin_client.post(
        f"/admin/review/maker/{pending_id}", json={"action": "approve"}
    )
    assert review.status_code == 200

    # Visible
    makers = await admin_client.get("/makers")
    data = makers.json()
    assert len(data) == 1
    assert data[0]["name"] == "Workflow Maker"


async def test_full_kiger_lifecycle_with_characters(admin_client):
    # 1. Submit and approve a character first
    char_submit = await admin_client.post("/character", json=CHAR_PAYLOAD)
    char_pending_id = int(char_submit.json()["id"])
    await admin_client.post(
        f"/admin/review/character/{char_pending_id}", json={"action": "approve"}
    )

    # Get the approved character's ID
    chars = await admin_client.get("/characters")
    char_id = chars.json()[0]["id"]

    # 2. Submit a kiger referencing that character
    kiger_payload = {
        **KIGER_PAYLOAD,
        "Characters": [
            {
                "characterId": str(char_id),
                "maker": "TestMaker",
                "images": ["https://example.com/img.png"],
            }
        ],
    }
    kiger_submit = await admin_client.post("/kiger", json=kiger_payload)
    assert kiger_submit.status_code == 200
    kiger_pending_id = kiger_submit.json()["id"]

    # 3. Approve the kiger
    review = await admin_client.post(
        f"/admin/review/kiger/{kiger_pending_id}", json={"action": "approve"}
    )
    assert review.status_code == 200

    # 4. Verify kiger is visible with character reference
    kigers = await admin_client.get("/kigers")
    assert len(kigers.json()) == 1

    detail = await admin_client.get(f"/kiger/{kiger_pending_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert data["name"] == "Workflow Kiger"
    assert len(data["Characters"]) == 1
    assert data["Characters"][0]["characterId"] == char_id


async def test_submit_and_reject(admin_client):
    # Submit
    submit = await admin_client.post("/character", json=CHAR_PAYLOAD)
    pending_id = int(submit.json()["id"])

    # Reject
    review = await admin_client.post(
        f"/admin/review/character/{pending_id}", json={"action": "reject"}
    )
    assert review.status_code == 200
    assert review.json()["status"] == "rejected"

    # Still empty
    chars = await admin_client.get("/characters")
    assert chars.json() == []


async def test_two_sequential_kiger_edits(admin_client):
    """Submit and approve first edit, then submit and approve second edit."""
    # 1. Create and approve initial kiger
    initial = await admin_client.post("/kiger", json=KIGER_PAYLOAD)
    kiger_id = initial.json()["id"]
    await admin_client.post(f"/admin/review/kiger/{kiger_id}", json={"action": "approve"})

    # 2. Edit 1: change bio only
    edit1 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "bio": "Updated bio"},
    )
    assert edit1.status_code == 200
    edit1_id = edit1.json()["id"]

    await admin_client.post(
        f"/admin/review/kiger/{edit1_id}", json={"action": "approve"}
    )

    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["bio"] == "Updated bio"
    assert detail.json()["name"] == "Workflow Kiger"  # Unchanged

    # 3. Edit 2: change name only (bio is now "Updated bio" in the DB)
    edit2 = await admin_client.post(
        "/kiger",
        json={
            **KIGER_PAYLOAD,
            "referenceId": kiger_id,
            "bio": "Updated bio",
            "name": "Updated Name",
        },
    )
    assert edit2.status_code == 200
    edit2_id = edit2.json()["id"]

    await admin_client.post(
        f"/admin/review/kiger/{edit2_id}", json={"action": "approve"}
    )

    # 4. Both changes must be visible
    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["name"] == "Updated Name"
    assert detail.json()["bio"] == "Updated bio"


async def test_two_simultaneous_pending_kiger_edits_different_fields(admin_client):
    """Two edits sit pending at the same time, each touching a different field."""
    # 1. Create and approve initial kiger
    initial = await admin_client.post("/kiger", json=KIGER_PAYLOAD)
    kiger_id = initial.json()["id"]
    await admin_client.post(f"/admin/review/kiger/{kiger_id}", json={"action": "approve"})

    # 2. Submit two edits simultaneously (neither approved yet)
    edit1 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "bio": "Bio from edit 1"},
    )
    edit2 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "name": "Name from edit 2"},
    )
    edit1_id = edit1.json()["id"]
    edit2_id = edit2.json()["id"]

    # Both should appear in the pending queue
    pending = await admin_client.get("/admin/pending/kigers")
    assert len(pending.json()) == 2

    # 3. Approve both edits
    await admin_client.post(
        f"/admin/review/kiger/{edit1_id}", json={"action": "approve"}
    )
    await admin_client.post(
        f"/admin/review/kiger/{edit2_id}", json={"action": "approve"}
    )

    # 4. Each change should be applied independently without clobbering the other
    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["bio"] == "Bio from edit 1"
    assert detail.json()["name"] == "Name from edit 2"


async def test_two_pending_edits_same_field_last_approval_wins(admin_client):
    """Two pending edits to the same field: the second approval overwrites the first."""
    # 1. Create and approve initial kiger
    initial = await admin_client.post("/kiger", json=KIGER_PAYLOAD)
    kiger_id = initial.json()["id"]
    await admin_client.post(f"/admin/review/kiger/{kiger_id}", json={"action": "approve"})

    # 2. Two edits both targeting 'name'
    edit1 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "name": "First Name"},
    )
    edit2 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "name": "Second Name"},
    )
    edit1_id = edit1.json()["id"]
    edit2_id = edit2.json()["id"]

    # 3. Approve edit 1 first
    await admin_client.post(
        f"/admin/review/kiger/{edit1_id}", json={"action": "approve"}
    )
    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["name"] == "First Name"

    # 4. Approve edit 2 — should overwrite edit 1's change
    await admin_client.post(
        f"/admin/review/kiger/{edit2_id}", json={"action": "approve"}
    )
    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["name"] == "Second Name"


async def test_reject_one_pending_edit_approve_other(admin_client):
    """Reject one pending kiger edit, approve the other; only approved change applies."""
    # 1. Create and approve initial kiger
    initial = await admin_client.post("/kiger", json=KIGER_PAYLOAD)
    kiger_id = initial.json()["id"]
    await admin_client.post(f"/admin/review/kiger/{kiger_id}", json={"action": "approve"})

    # 2. Submit two simultaneous edits
    edit1 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "bio": "Rejected bio"},
    )
    edit2 = await admin_client.post(
        "/kiger",
        json={**KIGER_PAYLOAD, "referenceId": kiger_id, "name": "Approved Name"},
    )
    edit1_id = edit1.json()["id"]
    edit2_id = edit2.json()["id"]

    # 3. Reject edit 1
    reject = await admin_client.post(
        f"/admin/review/kiger/{edit1_id}", json={"action": "reject"}
    )
    assert reject.json()["status"] == "rejected"

    # 4. Approve edit 2
    await admin_client.post(
        f"/admin/review/kiger/{edit2_id}", json={"action": "approve"}
    )

    # 5. Name changed, bio unchanged
    detail = await admin_client.get(f"/kiger/{kiger_id}")
    assert detail.json()["name"] == "Approved Name"
    assert detail.json()["bio"] == "Workflow bio"


async def test_admin_direct_update_bypasses_pending(admin_client, db_session):
    from api.database import Kiger as DBKiger

    kiger = DBKiger(
        id="direct-update-kiger",
        name="Original",
        bio="Original bio",
        is_active=True,
    )
    db_session.add(kiger)
    await db_session.commit()

    # Admin directly updates (no pending step)
    update_payload = {
        **KIGER_PAYLOAD,
        "name": "Directly Updated",
    }
    response = await admin_client.put(
        "/admin/kiger/direct-update-kiger", json=update_payload
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Directly Updated"

    # Visible immediately
    detail = await admin_client.get("/kiger/direct-update-kiger")
    assert detail.json()["name"] == "Directly Updated"
