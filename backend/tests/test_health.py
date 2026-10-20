def test_health_endpoint_returns_200(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_200_when_the_database_answers(client):
    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_returns_503_while_health_stays_200_when_the_database_is_down(client, monkeypatch):
    def refuse():
        raise ConnectionError("down")

    monkeypatch.setattr("app.main.check_database", refuse)

    assert client.get("/ready").status_code == 503
    assert client.get("/health").status_code == 200


def test_startup_refuses_to_boot_and_names_the_host_but_not_the_password(monkeypatch):
    import pytest
    from fastapi.testclient import TestClient

    from app.main import app

    def refuse():
        raise ConnectionError("password=hunter2")

    monkeypatch.setattr("app.main.check_database", refuse)
    monkeypatch.setattr(
        "app.main.settings.database_url", "postgresql+psycopg://postgres.ref:hunter2@pooler.example.com:6543/postgres"
    )

    with pytest.raises(RuntimeError) as raised:
        with TestClient(app):
            pass

    message = str(raised.value)
    assert "pooler.example.com:6543" in message
    assert "hunter2" not in message
    assert "postgres.ref" not in message


def test_startup_succeeds_when_the_database_answers(db_engine):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as started:
        assert started.get("/health").status_code == 200
