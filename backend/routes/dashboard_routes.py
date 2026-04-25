from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["Student Dashboard"])


@router.get("/stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get overall stats for the student dashboard."""
    submissions = db.query(models.Submission).filter(
        models.Submission.user_id == current_user.id,
        models.Submission.submitted_at.isnot(None),
    ).all()

    total = len(submissions)
    if total == 0:
        return schemas.DashboardStats(total_quizzes_taken=0, average_score=0.0, best_rank=None)

    avg_score = sum(s.score for s in submissions) / total
    best_rank = None
    for sub in submissions:
        all_subs = db.query(models.Submission).filter(
            models.Submission.quiz_id == sub.quiz_id,
            models.Submission.submitted_at.isnot(None),
        ).order_by(models.Submission.score.desc(), models.Submission.time_taken.asc()).all()
        rank = next((i + 1 for i, s in enumerate(all_subs) if s.id == sub.id), None)
        if rank and (best_rank is None or rank < best_rank):
            best_rank = rank

    return schemas.DashboardStats(total_quizzes_taken=total, average_score=round(avg_score, 2), best_rank=best_rank)


@router.get("/quizzes", response_model=List[schemas.DashboardQuizItem])
async def get_completed_quizzes(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all completed quizzes for the student dashboard."""
    submissions = db.query(models.Submission).filter(
        models.Submission.user_id == current_user.id,
        models.Submission.submitted_at.isnot(None),
    ).order_by(models.Submission.submitted_at.desc()).all()

    result = []
    for sub in submissions:
        quiz = db.query(models.Quiz).filter(models.Quiz.id == sub.quiz_id).first()
        all_subs = db.query(models.Submission).filter(
            models.Submission.quiz_id == sub.quiz_id,
            models.Submission.submitted_at.isnot(None),
        ).order_by(models.Submission.score.desc(), models.Submission.time_taken.asc()).all()
        rank = next((i + 1 for i, s in enumerate(all_subs) if s.id == sub.id), 0)
        result.append(schemas.DashboardQuizItem(
            submission_id=sub.id, quiz_id=sub.quiz_id,
            quiz_title=quiz.title if quiz else "Deleted Quiz",
            score=sub.score, time_taken=sub.time_taken,
            rank=rank, total_participants=len(all_subs), submitted_at=sub.submitted_at,
        ))
    return result
