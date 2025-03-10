import pytest
from unittest.mock import patch, MagicMock
from app.generator import generate_quiz
from app.models.quiz import QuizQuestion, QuizOutput


def test_generate_quiz_success():
    """Test successful quiz generation."""
    # Create a mock response that matches what OpenAI client returns
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = """
    {
        "questions": [
            {
                "question": "What is the capital of France?",
                "option_a": "Paris",
                "option_b": "London",
                "option_c": "Berlin",
                "option_d": "Madrid",
                "correct_answer": "a",
                "explanation": "Paris is the capital of France."
            }
        ]
    }
    """

    # Patch the OpenAI client's create method
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_response

    with patch("app.generator.client", mock_client):
        questions = generate_quiz(
            learning_objective="Name the capital of France", num_questions=1
        )

        assert len(questions) == 1
        assert questions[0].question == "What is the capital of France?"
        assert questions[0].correct_answer == "a"


def test_generate_quiz_error_handling():
    """Test error handling during quiz generation."""
    # Patch the OpenAI client to raise an exception
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = Exception("API Error")

    with patch("app.generator.client", mock_client):
        questions = generate_quiz(
            learning_objective="Test error handling", num_questions=1
        )

        assert len(questions) == 1
        assert "Error" in questions[0].question
