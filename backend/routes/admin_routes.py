import csv
import io
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from .. import models, schemas
from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/api/admin", tags=["Admin Analytics"])


@router.get("/quiz/{quiz_id}/submissions", response_model=List[schemas.SubmissionListItem])
async def get_all_submissions(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get all submissions for a quiz (admin only)."""
    submissions = db.query(models.Submission).filter(
        models.Submission.quiz_id == quiz_id,
        models.Submission.submitted_at.isnot(None),
    ).order_by(models.Submission.score.desc(), models.Submission.time_taken.asc()).all()

    result = []
    for sub in submissions:
        user = db.query(models.User).filter(models.User.id == sub.user_id).first()
        v_count = db.query(func.count(models.ProctorLog.id)).filter(
            models.ProctorLog.submission_id == sub.id).scalar()
        result.append(schemas.SubmissionListItem(
            id=sub.id, quiz_id=sub.quiz_id, user_id=sub.user_id,
            user_name=user.name if user else None, user_email=user.email if user else None,
            started_at=sub.started_at, submitted_at=sub.submitted_at,
            score=sub.score, time_taken=sub.time_taken,
            auto_submitted=sub.auto_submitted, violation_count=v_count,
        ))
    return result


@router.get("/quiz/{quiz_id}/question-stats", response_model=List[schemas.QuestionStat])
async def get_question_stats(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get per-question accuracy stats (admin only)."""
    questions = db.query(models.Question).filter(
        models.Question.quiz_id == quiz_id).order_by(models.Question.order_index).all()

    stats = []
    for q in questions:
        answers = db.query(models.Answer).filter(models.Answer.question_id == q.id).all()
        total = len(answers)
        correct = 0
        if q.type != "text":
            correct_opts = {o.id for o in q.options if o.is_correct}
            for a in answers:
                if set(a.selected_options or []) == correct_opts:
                    correct += 1
        stats.append(schemas.QuestionStat(
            question_id=q.id, question_text=q.text, question_type=q.type,
            total_answers=total, correct_answers=correct,
            accuracy_percent=round((correct / total * 100) if total > 0 else 0, 1),
        ))
    return stats


@router.get("/submission/{submission_id}/violations", response_model=List[schemas.ProctorLogOut])
async def get_violation_report(
    submission_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get full ProctorLog for a submission (admin only)."""
    logs = db.query(models.ProctorLog).filter(
        models.ProctorLog.submission_id == submission_id
    ).order_by(models.ProctorLog.timestamp).all()
    return logs


@router.get("/quiz/{quiz_id}/export")
async def export_results_csv(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Export all results as CSV (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    submissions = db.query(models.Submission).filter(
        models.Submission.quiz_id == quiz_id,
        models.Submission.submitted_at.isnot(None),
    ).order_by(models.Submission.score.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Name", "Email", "Score", "Time (s)", "Auto-Submitted", "Violations", "Submitted At"])

    for rank, sub in enumerate(submissions, start=1):
        user = db.query(models.User).filter(models.User.id == sub.user_id).first()
        v_count = db.query(func.count(models.ProctorLog.id)).filter(
            models.ProctorLog.submission_id == sub.id).scalar()
        writer.writerow([
            rank, user.name if user else "N/A", user.email if user else "N/A",
            sub.score, sub.time_taken, sub.auto_submitted, v_count,
            sub.submitted_at.isoformat() if sub.submitted_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=quiz_{quiz_id}_results.csv"},
    )
