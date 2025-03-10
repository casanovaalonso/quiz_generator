# tests/test_services/test_generator.py
import pytest
from unittest.mock import patch, MagicMock
from app.generator import generate_quiz
from app.models.quiz import QuizQuestion


@pytest.fixture
def quiz_generator():
    """Create a QuizGenerator instance for testing."""
    return QuizGenerator()


def test_generate_quiz_success(quiz_generator):
    """Test successful quiz generation."""
    # Mock the OpenAI response
    mock_content = """
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

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = mock_content

    with patch("openai.OpenAI.chat.completions.create", return_value=mock_response):
        questions = quiz_generator.generate_quiz(
            learning_objective="Name the capital of France", num_questions=1
        )

        assert len(questions) == 1
        assert questions[0].question == "What is the capital of France?"
        assert questions[0].correct_answer == "a"


def test_generate_quiz_error_handling(quiz_generator):
    """Test error handling during quiz generation."""
    with patch(
        "openai.OpenAI.chat.completions.create", side_effect=Exception("API Error")
    ):
        questions = quiz_generator.generate_quiz(
            learning_objective="Test error handling", num_questions=1
        )

        assert len(questions) == 1
        assert "Error" in questions[0].question
