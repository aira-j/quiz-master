from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from .. import models, schemas
from ..auth import hash_password, verify_password, create_access_token, get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.get("/check-setup")
async def check_setup(db: Session = Depends(get_db)):
    """Check if an admin account exists. Used by the first-run setup page."""
    admin_exists = db.query(models.User).filter(models.User.role == "admin").first() is not None
    return {"admin_exists": admin_exists}


@router.post("/admin/setup", response_model=schemas.Token)
async def admin_setup(admin: schemas.AdminCreate, db: Session = Depends(get_db)):
    """First-run admin account creation. Only works when no admin exists."""
    existing_admin = db.query(models.User).filter(models.User.role == "admin").first()
    if existing_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin account already exists",
        )

    # Check if email is already taken
    existing_user = db.query(models.User).filter(models.User.email == admin.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    db_user = models.User(
        name=admin.name,
        email=admin.email,
        password_hash=hash_password(admin.password),
        role="admin",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=schemas.Token)
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new participant account."""
    existing = db.query(models.User).filter(models.User.email == user.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    db_user = models.User(
        name=user.name,
        email=user.email,
        password_hash=hash_password(user.password),
        role=user.role if user.role else "participant",
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"sub": str(db_user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login", response_model=schemas.Token)
async def login(credentials: schemas.UserLogin, db: Session = Depends(get_db)):
    """Login with email and password. Returns JWT."""
    user = db.query(models.User).filter(models.User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=schemas.UserOut)
async def get_me(current_user: models.User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user
