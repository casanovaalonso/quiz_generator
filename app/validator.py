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
from models.quiz import QuizQuestion, ValidationResult

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
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
llm = ChatOpenAI(model=MODEL_NAME, temperature=0)
agent = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)


def validate_answer(
    question_text: str, correct_answer: str, explanation: str
) -> ValidationResult:
    """
    Validates only the correct answer of a quiz question.

    Args:
        question_text: The text of the quiz question
        correct_answer: The correct answer option text
        explanation: The explanation for why the answer is correct

    Returns:
        ValidationResult: An object containing validation outcome, explanation, and sources
    """
    instructions = """
    You are a validation agent for educational quiz questions. Your task is to validate whether the provided correct answer to a quiz question is factually accurate.

    To validate the answer:
    1. Generate search queries targeting academic information about the topic.
    2. Use the search tool to find relevant information.
    3. Analyze the search results to determine if the correct answer is supported by factual information.
    4. Focus only on determining if the provided correct answer is actually correct.
    5. If the information is inconclusive or contradictory, indicate that in the result.

    Once you have gathered enough information, provide your final answer in the following JSON format:
    {
        "is_correct": true/false/null,
        "explanation": "A brief explanation of your findings about the correctness of the answer",
        "sources": ["list", "of", "source", "URLs"]
    }
    - Set "is_correct" to true if the answer is verified correct, false if it's wrong, or null if inconclusive.
    - Include at least one source if possible.
    """

    claim = f"Question: '{question_text}'\nCorrect answer: '{correct_answer}'\nExplanation: {explanation}"

    try:
        logger.info(f"Validating claim: {claim[:100]}...")
        raw_result = agent.run(f"{instructions}\n\nAnswer to validate: {claim}")

        # Extract JSON from the result
        if "Final Answer:" in raw_result:
            final_answer = raw_result.split("Final Answer:")[-1].strip()
        else:
            json_match = re.search(r"({[\s\S]*})", raw_result)
            if json_match:
                final_answer = json_match.group(1)
            else:
                raise ValueError("No structured response found")

        result_dict = json.loads(final_answer)
        validation_result = ValidationResult(**result_dict)

    except json.JSONDecodeError:
        logger.error(f"JSON decode error for validation result: {raw_result}")
        validation_result = ValidationResult(
            is_correct=None,
            explanation="Could not determine if the answer is correct. The validation system failed to parse the results.",
            sources=[],
        )
    except Exception as e:
        logger.error(f"Error validating answer: {str(e)}")
        validation_result = ValidationResult(
            is_correct=None,
            explanation=f"Could not validate the answer: {str(e)}",
            sources=[],
        )

    return validation_result


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
