from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.chat import ChatSource

Difficulty = Literal["easy", "medium", "hard"]
QuestionType = Literal["multiple_choice"]

DEFAULT_QUANTITY = 5
MAX_QUANTITY = 10
MAX_OBSERVATION_CHARS = 500
MIN_CONTEXT_CHARS = 80
CHOICE_IDS = ("A", "B", "C", "D")


class GenerateQuestionsRequest(BaseModel):
    observation: str | None = Field(
        default=None,
        max_length=MAX_OBSERVATION_CHARS,
        description="Instrução opcional de estilo, quantidade desejada ou foco (não altera o formato JSON).",
    )
    quantity: int = Field(default=DEFAULT_QUANTITY, ge=1, le=MAX_QUANTITY)
    difficulty: Difficulty = "medium"
    question_type: QuestionType = "multiple_choice"

    @field_validator("observation", mode="before")
    @classmethod
    def blank_observation(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value


class QuestionChoice(BaseModel):
    id: str = Field(min_length=1, max_length=4)
    text: str = Field(min_length=1, max_length=500)


class GeneratedQuestion(BaseModel):
    stem: str = Field(min_length=1, max_length=2000, description="Enunciado.")
    choices: list[QuestionChoice] = Field(min_length=4, max_length=4)
    correct_option: str = Field(min_length=1, max_length=4)
    explanation: str = Field(min_length=1, max_length=4000)
    difficulty: Difficulty = "medium"

    @model_validator(mode="after")
    def correct_option_must_exist(self) -> "GeneratedQuestion":
        ids = [choice.id.upper() for choice in self.choices]
        if len(set(ids)) != len(ids):
            raise ValueError("As alternativas devem ter identificadores únicos.")
        answer = self.correct_option.strip().upper()
        if answer not in ids:
            raise ValueError("O gabarito não corresponde a nenhuma alternativa.")
        self.correct_option = answer
        for choice in self.choices:
            choice.id = choice.id.strip().upper()
        return self


class ModelQuestionsPayload(BaseModel):
    questions: list[GeneratedQuestion] = Field(min_length=1, max_length=MAX_QUANTITY)


class QuestionSetResponse(BaseModel):
    id: str
    conversation_id: str
    observation: str | None = None
    quantity: int
    difficulty: Difficulty
    question_type: QuestionType
    questions: list[GeneratedQuestion]
    used_documents: bool
    has_relevant_match: bool
    sources: list[ChatSource]
    model: str
    created_at: datetime


class QuestionSetListResponse(BaseModel):
    items: list[QuestionSetResponse]
    total: int
