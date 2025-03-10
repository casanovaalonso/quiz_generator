"""
Quiz Validator - Validation service for quiz questions
"""

import os
import json
import logging
import asyncio
from typing import List
import re
from dotenv import load_dotenv

# LangChain imports
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_community.utilities import DuckDuckGoSearchAPIWrapper
from langchain_openai import ChatOpenAI

# Import data models
from app.models.quiz import QuizQuestion, ValidationResult

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

# Set up DuckDuckGo search tool for validation agent
search = DuckDuckGoSearchAPIWrapper()


def duckduckgo_search(query: str) -> str:
    """Execute search using DuckDuckGo"""
    logger.info(f"Searching for: {query}")
    return search.run(query)


# Initialize tools for the validation agent
tools = [
    Tool(
        name="Search",
        func=duckduckgo_search,
        description="Useful for searching the web for information. Use targeted queries with academic terms.",
    )
]

# Initialize LangChain components
MODEL_NAME = os.getenv("VALIDATOR_OPENAI_MODEL", "gpt-4o-mini")
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
agent = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)


def validate_answer(
    question_text: str, correct_answer: str, explanation: str
) -> ValidationResult:
    instructions = """
    You are a validation agent for educational quiz questions. Your task is to validate whether the provided correct answer is factually accurate using ONLY the Search tool. Do not rely on prior knowledge.

    Steps:
    1. Generate a targeted search query for academic or authoritative information.
    2. Use the Search tool to gather results.
    3. Extract factual evidence and exact URLs from the search results.
    4. Determine if the correct answer is supported by this evidence.
    5. Return a JSON object:
       {
           "is_correct": true/false/null,
           "explanation": "Your findings based on search results",
           "sources": ["list", "of", "exact", "URLs", "from", "search"]
       }
    - 'sources' must contain only URLs directly from the search results, or be empty if none are found.
    """

    claim = f"Question: '{question_text}'\nCorrect answer: '{correct_answer}'\nExplanation: {explanation}"
    logger.info(f"Validating claim: {claim[:100]}...")

    try:
        raw_result = agent.run(f"{instructions}\n\nAnswer to validate: {claim}")
        logger.info(f"Raw agent result: {raw_result}")

        # Extract JSON
        json_match = re.search(r"({[\s\S]*})", raw_result)
        if not json_match:
            raise ValueError("No JSON found in response")
        result_dict = json.loads(json_match.group(1))

        # Clean sources
        cleaned_sources = [
            source
            for source in result_dict.get("sources", [])
            if source.startswith("http") and len(source) > 10  # Basic URL check
        ]
        result_dict["sources"] = cleaned_sources

        return ValidationResult(**result_dict)

    except Exception as e:
        logger.error(f"Validation error: {str(e)}")
        return ValidationResult(
            is_correct=None,
            explanation=f"Validation failed: {str(e)}",
            sources=[],
        )


async def validate_question(question: QuizQuestion) -> QuizQuestion:
    """
    Validates only the correct answer for a quiz question.

    Args:
        question: The quiz question to validate

    Returns:
        The question with validation results added
    """
    # Get the text of the correct answer option
    correct_option = getattr(question, f"option_{question.correct_answer}")

    # Validate only the correct answer
    validation_result = validate_answer(
        question_text=question.question,
        correct_answer=correct_option,
        explanation=question.explanation,
    )

    # Add validation results to the question
    question.validation = validation_result

    return question


async def validate_quiz_questions(questions: List[QuizQuestion]) -> List[QuizQuestion]:
    """
    Validates only the correct answers for all questions in a quiz.

    Args:
        questions: The list of quiz questions to validate

    Returns:
        The list of questions with validation results added
    """
    # Create validation tasks for each question
    validation_tasks = [validate_question(question) for question in questions]

    # Run validations in parallel
    validated_questions = await asyncio.gather(*validation_tasks)

    return validated_questions
