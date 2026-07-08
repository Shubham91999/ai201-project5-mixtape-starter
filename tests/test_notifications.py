"""
tests/test_notifications.py — Mixtape

Regression tests for notification behavior.
"""

import pytest
from app import create_app, db
from models import User, Song


@pytest.fixture
def app():
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def seed_rating_case(app):
    with app.app_context():
        owner = User(username="owner", email="owner@example.com")
        rater = User(username="rater", email="rater@example.com")
        db.session.add_all([owner, rater])
        db.session.flush()

        song = Song(
            title="Regression Anthem",
            artist="Debug Crew",
            shared_by=owner.id,
        )
        db.session.add(song)
        db.session.commit()

        yield {
            "owner": owner,
            "rater": rater,
            "song": song,
        }


def test_rating_creates_notification_for_song_owner(app, seed_rating_case):
    """Rating another user's shared song should create a song_rated notification."""
    with app.app_context():
        client = app.test_client()
        owner_id = seed_rating_case["owner"].id
        rater_id = seed_rating_case["rater"].id
        song_id = seed_rating_case["song"].id

        before = client.get(f"/users/{owner_id}/notifications").get_json()
        assert before["count"] == 0

        rate_resp = client.post(
            f"/songs/{song_id}/rate",
            json={"user_id": rater_id, "score": 5},
        )
        assert rate_resp.status_code == 201

        after = client.get(f"/users/{owner_id}/notifications").get_json()
        assert after["count"] == 1
        assert after["notifications"][0]["type"] == "song_rated"
