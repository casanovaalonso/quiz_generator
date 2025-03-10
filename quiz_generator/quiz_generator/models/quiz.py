from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Any


class ValidationResult(BaseModel):
    is_correct: Optional[bool] = None
    explanation: str
    sources: List[str] = []


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
    validation: Optional[ValidationResult] = None

    # Validators
    @field_validator(
        "question", "option_a", "option_b", "option_c", "option_d", "explanation"
    )
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("correct_answer")
    @classmethod
    def valid_answer(cls, v: str) -> str:
        if v not in ["a", "b", "c", "d"]:
            raise ValueError("Correct answer must be a, b, c, or d")
        return v

    def to_api_format(self) -> Dict[str, Any]:
        """Convert to API response format"""
        result = {
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

        if self.validation:
            result["validation"] = {
                "is_correct": self.validation.is_correct,
                "explanation": self.validation.explanation,
                "sources": self.validation.sources,
            }

        return result


class QuizOutput(BaseModel):
    questions: List[QuizQuestion]
