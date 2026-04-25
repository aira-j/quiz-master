from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/session", tags=["Quiz Session"])


@router.post("/start/{share_token}")
async def start_quiz(
    share_token: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Start a quiz attempt. Creates a Submission record."""
    # Find the quiz
    quiz = db.query(models.Quiz).filter(
        models.Quiz.share_token == share_token,
        models.Quiz.is_published == True,
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or not published")

    # Check expiry
    if quiz.expires_at and quiz.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="This quiz has expired")

    # Check for existing attempt (one attempt per user per quiz)
    existing = db.query(models.Submission).filter(
        models.Submission.quiz_id == quiz.id,
        models.Submission.user_id == current_user.id,
    ).first()
    if existing:
        # If they have an unsubmitted attempt, resume it
        if existing.submitted_at is None:
            questions = db.query(models.Question).filter(
                models.Question.quiz_id == quiz.id
            ).order_by(models.Question.order_index).all()

            saved_answers = db.query(models.Answer).filter(
                models.Answer.submission_id == existing.id
            ).all()

            violation_count = db.query(func.count(models.ProctorLog.id)).filter(
                models.ProctorLog.submission_id == existing.id
            ).scalar()

            return {
                "submission_id": existing.id,
                "quiz_id": quiz.id,
                "quiz_title": quiz.title,
                "time_limit": quiz.time_limit,
                "started_at": existing.started_at.isoformat(),
                "questions": [_question_to_public(q) for q in questions],
                "saved_answers": [_answer_to_dict(a) for a in saved_answers],
                "violation_count": violation_count,
                "resumed": True,
            }
        else:
            raise HTTPException(status_code=400, detail="You have already taken this quiz")

    # Create new submission
    submission = models.Submission(
        quiz_id=quiz.id,
        user_id=current_user.id,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # Get questions (without correct answers)
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == quiz.id
    ).order_by(models.Question.order_index).all()

    return {
        "submission_id": submission.id,
        "quiz_id": quiz.id,
        "quiz_title": quiz.title,
        "time_limit": quiz.time_limit,
        "started_at": submission.started_at.isoformat(),
        "questions": [_question_to_public(q) for q in questions],
        "saved_answers": [],
        "violation_count": 0,
        "resumed": False,
    }


@router.post("/{submission_id}/save")
async def save_answers(
    submission_id: int,
    data: schemas.AnswersBulkSave,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Auto-save answers (called every 30 seconds from client)."""
    submission = _get_active_submission(submission_id, current_user.id, db)

    for ans in data.answers:
        # Upsert: update if exists, create if not
        existing = db.query(models.Answer).filter(
            models.Answer.submission_id == submission_id,
            models.Answer.question_id == ans.question_id,
        ).first()

        if existing:
            existing.selected_options = ans.selected_options
            existing.text_response = ans.text_response
        else:
            db_answer = models.Answer(
                submission_id=submission_id,
                question_id=ans.question_id,
                selected_options=ans.selected_options,
                text_response=ans.text_response,
            )
            db.add(db_answer)

    db.commit()
    return {"message": "Answers saved", "count": len(data.answers)}


@router.post("/{submission_id}/submit")
async def submit_quiz(
    submission_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
    auto_submitted: bool = False,
):
    """Final quiz submission. Triggers auto-grading."""
    submission = _get_active_submission(submission_id, current_user.id, db)

    now = datetime.utcnow()
    submission.submitted_at = now
    submission.auto_submitted = auto_submitted
    submission.time_taken = int((now - submission.started_at).total_seconds())

    # Auto-grade MCQ and T/F questions
    _auto_grade(submission, db)

    db.commit()
    db.refresh(submission)

    return {
        "message": "Quiz submitted successfully",
        "score": submission.score,
        "time_taken": submission.time_taken,
        "auto_submitted": submission.auto_submitted,
    }


@router.get("/{submission_id}/status")
async def get_session_status(
    submission_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current session state (time remaining, saved answers)."""
    submission = db.query(models.Submission).filter(
        models.Submission.id == submission_id,
        models.Submission.user_id == current_user.id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == submission.quiz_id).first()
    elapsed = (datetime.utcnow() - submission.started_at).total_seconds()
    remaining = max(0, (quiz.time_limit * 60) - elapsed)

    saved_answers = db.query(models.Answer).filter(
        models.Answer.submission_id == submission_id
    ).all()

    violation_count = db.query(func.count(models.ProctorLog.id)).filter(
        models.ProctorLog.submission_id == submission_id
    ).scalar()

    return {
        "submission_id": submission.id,
        "is_submitted": submission.submitted_at is not None,
        "time_remaining_seconds": int(remaining),
        "saved_answers": [_answer_to_dict(a) for a in saved_answers],
        "violation_count": violation_count,
    }


@router.post("/{submission_id}/proctor")
async def log_violation(
    submission_id: int,
    log: schemas.ProctorLogCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a proctoring violation. Returns current violation count."""
    submission = _get_active_submission(submission_id, current_user.id, db)

    db_log = models.ProctorLog(
        submission_id=submission_id,
        event_type=log.event_type,
    )
    db.add(db_log)
    db.commit()

    violation_count = db.query(func.count(models.ProctorLog.id)).filter(
        models.ProctorLog.submission_id == submission_id
    ).scalar()

    # Check if 2 violations reached → auto-submit
    should_auto_submit = violation_count >= 2
    if should_auto_submit and submission.submitted_at is None:
        now = datetime.utcnow()
        submission.submitted_at = now
        submission.auto_submitted = True
        submission.time_taken = int((now - submission.started_at).total_seconds())
        _auto_grade(submission, db)
        db.commit()

    return {
        "violation_count": violation_count,
        "auto_submitted": should_auto_submit,
    }


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _get_active_submission(submission_id: int, user_id: int, db: Session) -> models.Submission:
    """Get an active (not yet submitted) submission belonging to the user."""
    submission = db.query(models.Submission).filter(
        models.Submission.id == submission_id,
        models.Submission.user_id == user_id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.submitted_at is not None:
        raise HTTPException(status_code=400, detail="Quiz already submitted")
    return submission


def _auto_grade(submission: models.Submission, db: Session):
    """Auto-grade MCQ and T/F answers. Text answers are left for manual review."""
    answers = db.query(models.Answer).filter(
        models.Answer.submission_id == submission.id
    ).all()

    total_score = 0.0

    for answer in answers:
        question = db.query(models.Question).filter(
            models.Question.id == answer.question_id
        ).first()
        if not question:
            continue

        if question.type == "text":
            # Text answers are graded manually by admin
            continue

        correct_options = db.query(models.Option).filter(
            models.Option.question_id == question.id,
            models.Option.is_correct == True,
        ).all()
        correct_ids = {opt.id for opt in correct_options}

        selected = set(answer.selected_options or [])

        if question.type in ("mcq_single", "tf"):
            # All-or-nothing for single answer questions
            if selected == correct_ids:
                total_score += 1.0

        elif question.type == "mcq_multi":
            # Partial credit, no penalty
            if len(correct_ids) > 0:
                correct_selections = len(selected & correct_ids)
                score = correct_selections / len(correct_ids)
                total_score += score

    submission.score = total_score


def _question_to_public(q: models.Question) -> dict:
    """Convert a question to public format (no correct answers)."""
    return {
        "id": q.id,
        "type": q.type,
        "text": q.text,
        "order_index": q.order_index,
        "options": [{"id": o.id, "text": o.text} for o in q.options],
    }


def _answer_to_dict(a: models.Answer) -> dict:
    return {
        "question_id": a.question_id,
        "selected_options": a.selected_options,
        "text_response": a.text_response,
    }
