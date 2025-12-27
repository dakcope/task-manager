from sqlalchemy import text


def test_create_task_returns_pending(client):
    resp = client.post(
        "/api/v1/tasks",
        json={"title": "test task", "description": "hello", "priority": "MEDIUM"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()

    assert "id" in data
    assert data["title"] == "test task"
    assert data["description"] == "hello"
    assert data["priority"] == "MEDIUM"
    assert data["status"] == "PENDING"
    assert data["created_at"] is not None


def test_get_task_by_id(client):
    create = client.post("/api/v1/tasks", json={"title": "t1", "priority": "LOW"})
    task_id = create.json()["id"]

    resp = client.get(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == task_id
    assert data["title"] == "t1"
    assert data["priority"] == "LOW"
    assert data["status"] == "PENDING"


def test_list_tasks_filters_and_pagination(client):
    client.post("/api/v1/tasks", json={"title": "a", "priority": "LOW"})
    client.post("/api/v1/tasks", json={"title": "b", "priority": "MEDIUM"})
    client.post("/api/v1/tasks", json={"title": "c", "priority": "HIGH"})

    resp = client.get("/api/v1/tasks", params={"priority": "HIGH", "limit": 20, "offset": 0})
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["limit"] == 20
    assert data["offset"] == 0
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "c"
    assert data["items"][0]["priority"] == "HIGH"


def test_cancel_task_pending_to_cancelled(client):
    create = client.post("/api/v1/tasks", json={"title": "to-cancel", "priority": "MEDIUM"})
    task_id = create.json()["id"]

    resp = client.delete(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == task_id
    assert data["status"] == "CANCELLED"


def test_cancel_task_conflict_for_non_cancellable_status(client, db_session):
    create = client.post("/api/v1/tasks", json={"title": "done", "priority": "MEDIUM"})
    task_id = create.json()["id"]

    db_session.execute(
        text("UPDATE tasks SET status='COMPLETED' WHERE id = :id"),
        {"id": task_id},
    )
    db_session.commit()

    resp = client.delete(f"/api/v1/tasks/{task_id}")
    assert resp.status_code == 409, resp.text