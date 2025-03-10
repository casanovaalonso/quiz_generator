"""
Quiz Generator - Generation service for creating quiz questions
"""

import os
import json
import logging
import asyncio
from typing import List
from openai import OpenAI
from dotenv import load_dotenv

# Import from local modules
from quiz_generator.models.quiz import QuizQuestion, QuizOutput
from quiz_generator.validator import validate_quiz_questions

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def generate_quiz(
    learning_objective: str, num_questions: int = 3, validate: bool = False
) -> List[QuizQuestion]:
    """
    Generate quiz questions based on a learning objective using the OpenAI API.

    Args:
        learning_objective: The learning objective to generate questions for
        num_questions: Number of questions to generate (default: 3)
        validate: Whether to validate the correct answers (default: False)

    Returns:
        A list of structured quiz questions
    """
    # System prompt for the quiz generation
    system_prompt = """
    You are an expert educational quiz generator specializing in creating high-quality, university-level quiz questions for higher education students. Your task is to generate multiple-choice questions that are challenging, specific, and aligned with academic rigor.

    Follow this structured approach for creating each question:
    1. **Thought**: Identify key concepts from the learning objective that require critical thinking
    2. **Action**: Create a specific, challenging question with four options (one correct)
    3. **Observation**: Verify the question meets university-level standards
    4. **Final Answer**: Format as required JSON

    OUTPUT REQUIREMENTS:
    You must produce ONLY a valid JSON object that conforms exactly to this schema:
    {
    "questions": [
        {
        "question": "Specific university-level question text",
        "option_a": "First plausible answer option",
        "option_b": "Second plausible answer option",
        "option_c": "Third plausible answer option",
        "option_d": "Fourth plausible answer option",
        "correct_answer": "a", // Must be lowercase a, b, c, or d only
        "explanation": "Brief explanation of why the answer is correct, referencing theories or concepts"
        }
        // Additional questions follow the same format
    ]
    }

    CRITICAL RULES:
    1. Output MUST be valid, parseable JSON with no additional text, markdown, or commentary
    2. Each question must be challenging and university-level
    3. Correct answer must be exactly one of: a, b, c, or d (lowercase)
    4. Do NOT include your reasoning process in the output JSON
    5. Ensure your answer is factually correct and can be verified by academic sources

    EXAMPLE OUTPUT FORMAT:
    {
    "questions": [
        {
        "question": "Which of the following best describes the principle of quantum superposition?",
        "option_a": "A quantum system can exist in multiple states simultaneously until measured",
        "option_b": "Quantum particles can teleport instantaneously between locations",
        "option_c": "Quantum systems always exist in discrete energy levels",
        "option_d": "The position and momentum of a particle cannot be simultaneously measured with precision",
        "correct_answer": "a",
        "explanation": "Quantum superposition allows quantum systems to exist as linear combinations of possible states, collapsing to a single state upon measurement, as formalized in quantum mechanical wave equations."
        }
    ]
    }
    """

    user_prompt = f"Generate {num_questions} questions for the learning objective: '{learning_objective}'."

    try:
        logger.info(
            f"Generating quiz: {num_questions} questions on '{learning_objective}'"
        )

        # Request JSON output format from OpenAI
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )

        # Extract the response content
        raw_content = completion.choices[0].message.content
        logger.debug(f"Raw content: {raw_content[:200]}...")  # Log first 200 chars only

        # Parse the JSON content
        data = json.loads(raw_content)

        # Validate with Pydantic
        quiz_output = QuizOutput.model_validate(data)
        generated_questions = quiz_output.questions

        # Validate questions if requested
        if validate:
            logger.info("Validating correct answers for quiz questions")
            # We need to run the async validation in a synchronous context
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            validated_questions = loop.run_until_complete(
                validate_quiz_questions(generated_questions)
            )
            loop.close()
            return validated_questions
        else:
            return generated_questions

    except Exception as e:
        logger.error(f"Error generating quiz questions: {str(e)}")

        # Fallback: try to extract JSON if possible
        try:
            if "raw_content" in locals():
                # Try to extract JSON if it's embedded in other text
                import re

                json_pattern = r"({[\s\S]*})"
                matches = re.findall(json_pattern, raw_content)

                if matches:
                    # Try each potential JSON match
                    for potential_json in matches:
                        try:
                            data = json.loads(potential_json)
                            # Validate with Pydantic
                            quiz_output = QuizOutput.model_validate(data)
                            return quiz_output.questions
                        except:
                            continue
        except:
            pass

        # Last resort: return a dummy question indicating the error
        return [
            QuizQuestion(
                question=f"Error generating quiz question: {str(e)}",
                option_a="Contact administrator",
                option_b="Try again later",
                option_c="Provide a different learning objective",
                option_d="Check API configuration",
                correct_answer="c",
                explanation="Failed to generate valid quiz data due to an error in processing the request.",
            )
        ]
