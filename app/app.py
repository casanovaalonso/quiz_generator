import os
import json
import logging
import asyncio
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Import from local modules
from app.generator import generate_quiz
from app.validator import validate_quiz_questions
from app.models.quiz import QuizQuestion, QuizOutput, ValidationResult

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.getenv("ALLOWED_ORIGINS", "*")}})

# Configuration
PORT = int(os.getenv("PORT", "5000"))
DEFAULT_NUM_QUESTIONS = int(os.getenv("DEFAULT_NUM_QUESTIONS", "3"))
MAX_NUM_QUESTIONS = int(os.getenv("MAX_NUM_QUESTIONS", "10"))
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz_endpoint():
    """Generate quiz questions API endpoint"""
    try:
        data = request.get_json()

        # Extract and validate parameters
        learning_objective = data.get("learning_objective", "")
        num_questions = data.get("num_questions", DEFAULT_NUM_QUESTIONS)
        validate = data.get("validate", False)

        # Input validation
        if not learning_objective:
            return jsonify({"error": "Learning objective is required"}), 400

        # Limit number of questions
        num_questions = max(1, min(MAX_NUM_QUESTIONS, num_questions))

        # Generate quiz questions
        quiz_questions = generate_quiz(learning_objective, num_questions, validate)
        quiz_data = {"questions": [q.to_api_format() for q in quiz_questions]}

        return jsonify(quiz_data)
    except Exception as e:
        logger.error(f"Error generating quiz: {str(e)}")
        return jsonify({"error": f"Failed to generate quiz: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=DEBUG_MODE)
