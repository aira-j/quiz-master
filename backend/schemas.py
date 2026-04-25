from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ──────────────────────────────────────────
# Auth Schemas
# ──────────────────────────────────────────

class UserCreate(BaseModel):
    name: str
    email: str
    password: str

class AdminCreate(BaseModel):
    name: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Option Schemas
# ──────────────────────────────────────────

class OptionCreate(BaseModel):
    text: str
    is_correct: bool = False

class OptionOut(BaseModel):
    id: int
    text: str
    is_correct: bool

    class Config:
        from_attributes = True

class OptionPublic(BaseModel):
    """Option without correct answer — shown to participants during quiz."""
    id: int
    text: str

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Question Schemas
# ──────────────────────────────────────────

class QuestionCreate(BaseModel):
    type: str  # mcq_single, mcq_multi, tf, text
    text: str
    order_index: Optional[int] = None
    options: List[OptionCreate] = []

class QuestionUpdate(BaseModel):
    type: Optional[str] = None
    text: Optional[str] = None
    order_index: Optional[int] = None
    options: Optional[List[OptionCreate]] = None

class QuestionOut(BaseModel):
    id: int
    type: str
    text: str
    order_index: int
    options: List[OptionOut] = []

    class Config:
        from_attributes = True

class QuestionPublic(BaseModel):
    """Question without correct answers — shown to participants."""
    id: int
    type: str
    text: str
    order_index: int
    options: List[OptionPublic] = []

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Quiz Schemas
# ──────────────────────────────────────────

class QuizCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    time_limit: int  # in minutes
    expires_at: Optional[datetime] = None

class QuizUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    time_limit: Optional[int] = None
    expires_at: Optional[datetime] = None

class QuizOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    time_limit: int
    share_token: str
    is_published: bool
    expires_at: Optional[datetime]
    created_at: datetime
    questions: List[QuestionOut] = []
    submission_count: Optional[int] = 0

    class Config:
        from_attributes = True

class QuizListItem(BaseModel):
    id: int
    title: str
    description: Optional[str]
    time_limit: int
    share_token: str
    is_published: bool
    expires_at: Optional[datetime]
    created_at: datetime
    submission_count: int = 0
    question_count: int = 0

    class Config:
        from_attributes = True

class QuizPublic(BaseModel):
    """Quiz info shown to participants via share link — no answers."""
    id: int
    title: str
    description: Optional[str]
    time_limit: int
    question_count: int = 0

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Submission / Answer Schemas
# ──────────────────────────────────────────

class AnswerSave(BaseModel):
    question_id: int
    selected_options: Optional[List[int]] = None
    text_response: Optional[str] = None

class AnswersBulkSave(BaseModel):
    answers: List[AnswerSave]

class AnswerOut(BaseModel):
    id: int
    question_id: int
    selected_options: Optional[List[int]]
    text_response: Optional[str]
    admin_score: Optional[float]

    class Config:
        from_attributes = True

class SubmissionOut(BaseModel):
    id: int
    quiz_id: int
    user_id: int
    started_at: datetime
    submitted_at: Optional[datetime]
    score: float
    time_taken: Optional[int]
    auto_submitted: bool
    answers: List[AnswerOut] = []

    class Config:
        from_attributes = True

class SubmissionListItem(BaseModel):
    id: int
    quiz_id: int
    user_id: int
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    started_at: datetime
    submitted_at: Optional[datetime]
    score: float
    time_taken: Optional[int]
    auto_submitted: bool
    violation_count: int = 0

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Leaderboard Schema
# ──────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    rank: int
    user_id: int
    user_name: str
    score: float
    time_taken: Optional[int]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Proctor Log Schema
# ──────────────────────────────────────────

class ProctorLogCreate(BaseModel):
    event_type: str  # tab_switch, fullscreen_exit, face_absent, face_multiple

class ProctorLogOut(BaseModel):
    id: int
    event_type: str
    timestamp: datetime

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Dashboard Schemas
# ──────────────────────────────────────────

class DashboardStats(BaseModel):
    total_quizzes_taken: int
    average_score: float
    best_rank: Optional[int]

class DashboardQuizItem(BaseModel):
    submission_id: int
    quiz_id: int
    quiz_title: str
    score: float
    time_taken: Optional[int]
    rank: int
    total_participants: int
    submitted_at: Optional[datetime]

    class Config:
        from_attributes = True


# ──────────────────────────────────────────
# Admin Analytics Schemas
# ──────────────────────────────────────────

class QuestionStat(BaseModel):
    question_id: int
    question_text: str
    question_type: str
    total_answers: int
    correct_answers: int
    accuracy_percent: float

class TextAnswerReview(BaseModel):
    question_id: Optional[int] = None
    answer_id: Optional[int] = None
    score: float
