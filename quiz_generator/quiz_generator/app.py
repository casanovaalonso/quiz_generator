import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
from typing import List

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()

# Configure OpenAI API with LangChain
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes


# Define the QuizQuestion Pydantic model
class QuizQuestion(BaseModel):
    question: str = Field(
        description="The quiz question text, specific and university-level"
    )
    option_a: str = Field(
        description="First answer option, plausible and subject-specific"
    )
    option_b: str = Field(
        description="Second answer option, plausible and subject-specific"
    )
    option_c: str = Field(
        description="Third answer option, plausible and subject-specific"
    )
    option_d: str = Field(
        description="Fourth answer option, plausible and subject-specific"
    )
    correct_answer: str = Field(
        description="The correct answer (a, b, c, or d)", pattern="^[a-d]$"
    )
    explanation: str = Field(
        description="Brief explanation of the correct answer, referencing advanced concepts or theories"
    )

    class Config:
        json_encoders = {
            str: lambda v: v.strip()  # Ensure strings are trimmed of extra whitespace
        }

    # Convert to the required API response format
    def to_api_format(self):
        return {
            "question": self.question,
            "options": {
                "a": self.option_a,
                "b": self.option_b,
                "c": self.option_c,
                "d": self.option_d,
            },
            "correct_answer": self.correct_answer,
            "explanation": self.explanation,
        }


def generate_quiz(
    learning_objective: str, num_questions: int = 3
) -> List[QuizQuestion]:
    """
    Generate quiz questions based on a learning objective using the OpenAI API with ReAct prompting.

    Args:
        learning_objective (str): The learning objective (e.g., "Balance chemical equations").
        num_questions (int): Number of questions to generate (default: 3).

    Returns:
        List[QuizQuestion]: A list of structured quiz questions.
    """
    system_prompt = """
    You are an expert educational quiz generator specializing in creating high-quality, university-level quiz questions for higher education students. Your task is to generate multiple-choice questions that are challenging, specific, and aligned with the academic rigor expected at the university degree level. Use the ReAct (Reasoning + Acting) technique to think through and construct each question step-by-step.

    For each question, follow this ReAct process:
    1. **Thought**: Analyze the provided learning objective. Identify key concepts, theories, models, or methodologies relevant to the subject at a university level. Consider how to make the question require critical thinking, application, or synthesis rather than simple recall.
    2. **Action**: Formulate a specific, challenging question based on your analysis. Design four answer options (a, b, c, d) with exactly one correct answer and plausible distractors. Draft an explanation that justifies the correct answer using advanced subject knowledge.
    3. **Observation**: Reflect on the question. Ensure it avoids generic or simplistic content, aligns with the learning objective, and meets university-level standards. Adjust if necessary to increase specificity or rigor.
    4. **Final Answer**: Present the completed question in the required JSON format.

    Each question must:
    - Be directly relevant to the provided learning objective.
    - Have exactly four answer options labeled a, b, c, d.
    - Have exactly one correct answer, clearly indicated.
    - Require critical thinking, application of advanced concepts, or synthesis of information rather than simple recall.
    - Be deeply rooted in the subject matter, referencing specific theories, models, case studies, or methodologies where appropriate.
    - Avoid generic, overly broad, or simplistic content that could be answered with basic knowledge.

    Examples of the expected level:
    - Instead of 'What is the law of conservation of mass?', think: 'How can I test understanding of this law in a complex scenario?' Then act: 'How does the law of conservation of mass apply to balancing chemical equations in redox reactions involving transition metals?' with options reflecting nuanced understanding.
    - Instead of 'What is DNA?', reason: 'I’ll focus on a specific process like replication.' Then act: 'Which of the following best describes the role of DNA polymerase in eukaryotic DNA replication?' with detailed options.

    Ensure the questions are suitable for university students (undergraduate or postgraduate level) and expressed in clear, professional English.

    Format your response as a JSON array of objects, where each object contains:
    - question: string
    - option_a: string
    - option_b: string
    - option_c: string
    - option_d: string
    - correct_answer: string ("a", "b", "c", or "d")
    - explanation: string (a brief explanation of why the correct answer is right, referencing specific concepts or theories)

    Structure your response to include your reasoning steps for clarity, followed by the final JSON output. Use this format for each question:
    [Thought: Your reasoning about the learning objective and question design]
    [Action: Constructing the question, options, and explanation]
    [Observation: Reflection on the question’s quality and adjustments]
    [Final Answer: {"question": "...", "option_a": "...", ...}]

    Ensure the final output is a strictly JSON-formatted array with no additional text outside the array, containing only the 'Final Answer' content for each question. Wrap all Final Answers in a single JSON array at the end of your response, enclosed in square brackets [ ]. Do not include any text before or after the JSON array in the final output.
    """

    user_prompt = f"Generate {num_questions} questions for the learning objective: '{learning_objective}'."

    response = llm.invoke(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )

    raw_content = response.content.strip()
    app.logger.debug(f"Raw generator response: '{raw_content}'")

    try:
        # Extract the JSON array from the response
        # Look for the last JSON array in the response (after reasoning steps)
        json_start = raw_content.rfind("[")
        json_end = raw_content.rfind("]") + 1
        if json_start == -1 or json_end == -1 or json_start >= json_end:
            raise ValueError("No valid JSON array found in the response")

        json_str = raw_content[json_start:json_end]
        quiz_data = json.loads(json_str)

        if not isinstance(quiz_data, list):
            raise ValueError("Parsed response is not a JSON array")

        quiz_questions = [QuizQuestion(**question) for question in quiz_data]
        return quiz_questions

    except (json.JSONDecodeError, ValueError) as e:
        app.logger.error(f"Error parsing response: {str(e)}")
        return [
            QuizQuestion(
                question="Error generating quiz question",
                option_a="N/A",
                option_b="N/A",
                option_c="N/A",
                option_d="N/A",
                correct_answer="a",
                explanation="Failed to generate valid quiz data due to an API error.",
            )
        ]


@app.route("/generate-quiz", methods=["POST"])
def generate_quiz_endpoint():
    try:
        data = request.get_json()
        learning_objective = data.get("learning_objective", "")
        num_questions = data.get("num_questions", 3)  # Default to 3 questions

        if not learning_objective:
            return jsonify({"error": "Learning objective is required"}), 400

        # Validate number of questions (between 1 and 10)
        num_questions = max(1, min(10, num_questions))

        # Generate questions
        quiz_questions = generate_quiz(learning_objective, num_questions)

        # Convert to API response format
        quiz_data = {"questions": [q.to_api_format() for q in quiz_questions]}

        # Return the generated questions
        return jsonify(quiz_data)

    except Exception as e:
        app.logger.error(f"Error generating quiz: {str(e)}")
        return jsonify({"error": f"Failed to generate quiz: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
