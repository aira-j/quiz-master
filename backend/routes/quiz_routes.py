from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from .. import models, schemas
from ..auth import require_admin
from ..database import get_db

router = APIRouter(prefix="/api/quizzes", tags=["Quizzes"])


# ──────────────────────────────────────────
# Quiz CRUD
# ──────────────────────────────────────────

@router.post("", response_model=schemas.QuizOut)
async def create_quiz(
    quiz: schemas.QuizCreate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a new quiz (admin only)."""
    db_quiz = models.Quiz(
        title=quiz.title,
        description=quiz.description,
        time_limit=quiz.time_limit,
        created_by=admin.id,
        expires_at=quiz.expires_at,
    )
    db.add(db_quiz)
    db.commit()
    db.refresh(db_quiz)

    return _quiz_to_out(db_quiz, db)


@router.get("", response_model=List[schemas.QuizListItem])
async def list_quizzes(
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all quizzes with submission and question counts (admin only)."""
    quizzes = db.query(models.Quiz).filter(models.Quiz.created_by == admin.id).order_by(models.Quiz.created_at.desc()).all()
    result = []
    for q in quizzes:
        sub_count = db.query(func.count(models.Submission.id)).filter(models.Submission.quiz_id == q.id).scalar()
        q_count = db.query(func.count(models.Question.id)).filter(models.Question.quiz_id == q.id).scalar()
        result.append(schemas.QuizListItem(
            id=q.id,
            title=q.title,
            description=q.description,
            time_limit=q.time_limit,
            share_token=q.share_token,
            is_published=q.is_published,
            expires_at=q.expires_at,
            created_at=q.created_at,
            submission_count=sub_count,
            question_count=q_count,
        ))
    return result


@router.get("/{quiz_id}", response_model=schemas.QuizOut)
async def get_quiz(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Get a quiz with all questions and options (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == admin.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return _quiz_to_out(quiz, db)


@router.put("/{quiz_id}", response_model=schemas.QuizOut)
async def update_quiz(
    quiz_id: int,
    quiz_update: schemas.QuizUpdate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update quiz metadata (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == admin.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if quiz_update.title is not None:
        quiz.title = quiz_update.title
    if quiz_update.description is not None:
        quiz.description = quiz_update.description
    if quiz_update.time_limit is not None:
        quiz.time_limit = quiz_update.time_limit
    if quiz_update.expires_at is not None:
        quiz.expires_at = quiz_update.expires_at

    db.commit()
    db.refresh(quiz)
    return _quiz_to_out(quiz, db)


@router.delete("/{quiz_id}")
async def delete_quiz(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a quiz and all related data (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == admin.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    db.delete(quiz)
    db.commit()
    return {"message": "Quiz deleted"}


@router.post("/{quiz_id}/publish")
async def toggle_publish(
    quiz_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Toggle quiz published/draft status (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == admin.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Require at least one question to publish
    q_count = db.query(func.count(models.Question.id)).filter(models.Question.quiz_id == quiz.id).scalar()
    if not quiz.is_published and q_count == 0:
        raise HTTPException(status_code=400, detail="Cannot publish a quiz with no questions")

    quiz.is_published = not quiz.is_published
    db.commit()
    return {"is_published": quiz.is_published, "share_token": quiz.share_token}


# ──────────────────────────────────────────
# Question CRUD
# ──────────────────────────────────────────

@router.post("/{quiz_id}/questions", response_model=schemas.QuestionOut)
async def add_question(
    quiz_id: int,
    question: schemas.QuestionCreate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Add a question to a quiz (admin only)."""
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id, models.Quiz.created_by == admin.id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Auto-assign order_index if not provided
    if question.order_index is None:
        max_order = db.query(func.max(models.Question.order_index)).filter(models.Question.quiz_id == quiz_id).scalar()
        question.order_index = (max_order or 0) + 1

    db_question = models.Question(
        quiz_id=quiz_id,
        type=question.type,
        text=question.text,
        order_index=question.order_index,
    )
    db.add(db_question)
    db.commit()
    db.refresh(db_question)

    # Add options
    for opt in question.options:
        db_option = models.Option(
            question_id=db_question.id,
            text=opt.text,
            is_correct=opt.is_correct,
        )
        db.add(db_option)

    db.commit()
    db.refresh(db_question)
    return db_question


@router.put("/{quiz_id}/questions/{question_id}", response_model=schemas.QuestionOut)
async def update_question(
    quiz_id: int,
    question_id: int,
    question_update: schemas.QuestionUpdate,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Update a question and its options (admin only)."""
    question = db.query(models.Question).filter(
        models.Question.id == question_id,
        models.Question.quiz_id == quiz_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    if question_update.type is not None:
        question.type = question_update.type
    if question_update.text is not None:
        question.text = question_update.text
    if question_update.order_index is not None:
        question.order_index = question_update.order_index

    # Replace options if provided
    if question_update.options is not None:
        # Delete existing options
        db.query(models.Option).filter(models.Option.question_id == question_id).delete()
        # Add new options
        for opt in question_update.options:
            db_option = models.Option(
                question_id=question_id,
                text=opt.text,
                is_correct=opt.is_correct,
            )
            db.add(db_option)

    db.commit()
    db.refresh(question)
    return question


@router.delete("/{quiz_id}/questions/{question_id}")
async def delete_question(
    quiz_id: int,
    question_id: int,
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a question (admin only)."""
    question = db.query(models.Question).filter(
        models.Question.id == question_id,
        models.Question.quiz_id == quiz_id,
    ).first()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    db.delete(question)
    db.commit()
    return {"message": "Question deleted"}


@router.put("/{quiz_id}/questions/reorder")
async def reorder_questions(
    quiz_id: int,
    question_ids: List[int],
    admin: models.User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Reorder questions by providing ordered list of question IDs (admin only)."""
    for index, qid in enumerate(question_ids, start=1):
        question = db.query(models.Question).filter(
            models.Question.id == qid,
            models.Question.quiz_id == quiz_id,
        ).first()
        if question:
            question.order_index = index

    db.commit()
    return {"message": "Questions reordered"}


# ──────────────────────────────────────────
# Public Quiz Access (via share token)
# ──────────────────────────────────────────

@router.get("/share/{share_token}", response_model=schemas.QuizPublic)
async def get_quiz_by_share_token(
    share_token: str,
    db: Session = Depends(get_db),
):
    """Get quiz info via share link (public — no answers exposed)."""
    quiz = db.query(models.Quiz).filter(
        models.Quiz.share_token == share_token,
        models.Quiz.is_published == True,
    ).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found or not published")

    q_count = db.query(func.count(models.Question.id)).filter(models.Question.quiz_id == quiz.id).scalar()
    return schemas.QuizPublic(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        time_limit=quiz.time_limit,
        question_count=q_count,
    )


# ──────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────

def _quiz_to_out(quiz: models.Quiz, db: Session) -> schemas.QuizOut:
    sub_count = db.query(func.count(models.Submission.id)).filter(models.Submission.quiz_id == quiz.id).scalar()
    return schemas.QuizOut(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        time_limit=quiz.time_limit,
        share_token=quiz.share_token,
        is_published=quiz.is_published,
        expires_at=quiz.expires_at,
        created_at=quiz.created_at,
        questions=quiz.questions,
        submission_count=sub_count,
    )
