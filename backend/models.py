import datetime
import uuid
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, JSON, Float
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    role = Column(String)  # 'admin' or 'participant'
    password_hash = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    quizzes_created = relationship("Quiz", back_populates="creator")
    submissions = relationship("Submission", back_populates="user")

class Quiz(Base):
    __tablename__ = "quizzes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    description = Column(Text)
    time_limit = Column(Integer)  # in minutes
    created_by = Column(Integer, ForeignKey("users.id"))
    share_token = Column(String, unique=True, default=lambda: str(uuid.uuid4()))
    is_published = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    creator = relationship("User", back_populates="quizzes_created")
    questions = relationship("Question", back_populates="quiz", cascade="all, delete-orphan")
    submissions = relationship("Submission", back_populates="quiz")

class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    type = Column(String)  # mcq_single, mcq_multi, tf, text
    text = Column(Text)
    order_index = Column(Integer)

    quiz = relationship("Quiz", back_populates="questions")
    options = relationship("Option", back_populates="question", cascade="all, delete-orphan")
    answers = relationship("Answer", back_populates="question")

class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    text = Column(Text)
    is_correct = Column(Boolean, default=False)

    question = relationship("Question", back_populates="options")

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    quiz_id = Column(Integer, ForeignKey("quizzes.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    submitted_at = Column(DateTime, nullable=True)
    score = Column(Float, default=0.0)
    time_taken = Column(Integer, nullable=True)  # in seconds
    auto_submitted = Column(Boolean, default=False)

    user = relationship("User", back_populates="submissions")
    quiz = relationship("Quiz", back_populates="submissions")
    answers = relationship("Answer", back_populates="submission")
    proctor_logs = relationship("ProctorLog", back_populates="submission")

class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    selected_options = Column(JSON, nullable=True)  # List of option IDs
    text_response = Column(Text, nullable=True)
    admin_score = Column(Float, nullable=True)

    submission = relationship("Submission", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class ProctorLog(Base):
    __tablename__ = "proctor_logs"

    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    event_type = Column(String)  # tab_switch, fullscreen_exit, face_absent, face_multiple
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)

    submission = relationship("Submission", back_populates="proctor_logs")
