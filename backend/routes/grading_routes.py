from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from .. import models, schemas
from ..auth import get_current_user, require_admin
from ..database import get_db

router = APIRouter(prefix="/api/grading", tags=["Grading & Results"])


@router.get("/{quiz_id}/leaderboard", response_model=List[schemas.LeaderboardEntry])
async def get_leaderboard(
    quiz_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get leaderboard for a quiz. Only accessible after participant has submitted."""
    # Check if the user has submitted this quiz
    user_submission = db.query(models.Submission).filter(
        models.Submission.quiz_id == quiz_id,
        models.Submission.user_id == current_user.id,
        models.Submission.submitted_at.isnot(None),
    ).first()

    # Admins can always view; participants only after submitting
    if current_user.role != "admin" and not user_submission:
        raise HTTPException(status_code=403, detail="Submit the quiz first to view the leaderboard")

    # Get all submitted entries, ordered by score desc then time_taken asc
    submissions = db.query(models.Submission).filter(
        models.Submission.quiz_id == quiz_id,
        models.Submission.submitted_at.isnot(None),
    ).order_by(
        models.Submission.score.desc(),
        models.Submission.time_taken.asc(),
    ).all()

    leaderboard = []
    for rank, sub in enumerate(submissions, start=1):
        user = db.query(models.User).filter(models.User.id == sub.user_id).first()
        leaderboard.append(schemas.LeaderboardEntry(
            rank=rank,
            user_id=sub.user_id,
            user_name=user.name if user else "Unknown",
            score=sub.score,
            time_taken=sub.time_taken,
        ))

    return leaderboard


@router.get("/{submission_id}/result")
async def get_result(
    submission_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get detailed result for a submission."""
    submission = db.query(models.Submission).filter(
        models.Submission.id == submission_id,
    ).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Only the owner or admin can view
    if submission.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    if submission.submitted_at is None:
        raise HTTPException(status_code=400, detail="Quiz not yet submitted")

    quiz = db.query(models.Quiz).filter(models.Quiz.id == submission.quiz_id).first()
    answers = db.query(models.Answer).filter(
        models.Answer.submission_id == submission_id
    ).all()

    # Build question-by-question breakdown
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == submission.quiz_id
    ).order_by(models.Question.order_index).all()

    breakdown = []
    for q in questions:
        answer = next((a for a in answers if a.question_id == q.id), None)
        correct_options = [o for o in q.options if o.is_correct]
        correct_ids = [o.id for o in correct_options]

        selected = answer.selected_options if answer else []
        text_resp = answer.text_response if answer else None

        # Determine if correct
        is_correct = None
        if q.type == "text":
            is_correct = None  # Pending admin review
            if answer and answer.admin_score is not None:
                is_correct = answer.admin_score > 0
        elif q.type in ("mcq_single", "tf"):
            is_correct = set(selected or []) == set(correct_ids)
        elif q.type == "mcq_multi":
            is_correct = set(selected or []) == set(correct_ids)

        breakdown.append({
            "question_id": q.id,
            "question_text": q.text,
            "question_type": q.type,
            "selected_options": selected,
            "correct_options": correct_ids,
            "text_response": text_resp,
            "admin_score": answer.admin_score if answer else None,
            "is_correct": is_correct,
            "options": [{"id": o.id, "text": o.text, "is_correct": o.is_correct} for o in q.options],
        })

    # Get rank
    all_subs = db.query(models.Submission).filter(
        models.Submission.quiz_id == submission.quiz_id,
        models.Submission.submitted_at.isnot(None),
    ).order_by(
        models.Submission.score.desc(),
        models.Submission.time_taken.asc(),
    ).all()
    rank = next((i + 1 for i, s in enumerate(all_subs) if s.id == submission.id), None)

    return {
        "submission_id": submission.id,
        "quiz_id": submission.quiz_id,
        "quiz_title": quiz.title if quiz else "",
        "score": submission.score,
        "time_taken": submission.time_taken,
        "auto_submitted": submission.auto_submitted,
        "rank": rank,
        "total_participants": len(all_subs),
        "breakdown": breakdown,
    }


@router.post("/{submission_id}/mark-text")
async def mark_text_answer(
    submission_id: int,
    review: schemas.TextAnswerReview,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin manually scores a text-input answer."""
    answer = None
    if review.answer_id:
        answer = db.query(models.Answer).filter(
            models.Answer.id == review.answer_id,
            models.Answer.submission_id == submission_id,
        ).first()
    elif review.question_id:
        answer = db.query(models.Answer).filter(
            models.Answer.question_id == review.question_id,
            models.Answer.submission_id == submission_id,
        ).first()

    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")

    question = db.query(models.Question).filter(models.Question.id == answer.question_id).first()
    if not question or question.type != "text":
        raise HTTPException(status_code=400, detail="This answer is not a text-input type")

    old_score = answer.admin_score or 0.0
    answer.admin_score = review.score

    # Update submission total score
    submission = db.query(models.Submission).filter(models.Submission.id == submission_id).first()
    submission.score = submission.score - old_score + review.score

    db.commit()
    return {"message": "Text answer scored", "new_total_score": submission.score}

