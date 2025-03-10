import json
import pytest
from app.app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_generate_quiz_endpoint(client):
    """Test the /generate-quiz endpoint."""
    # Mock data to send in the request
    data = {
        "learning_objective": "Test learning objective",
        "num_questions": 1,
        "validate": False,
    }

    # Make request to the endpoint
    response = client.post(
        "/generate-quiz", data=json.dumps(data), content_type="application/json"
    )

    # Assert response status code and structure
    assert response.status_code == 200
    response_data = json.loads(response.data)
    assert "questions" in response_data
