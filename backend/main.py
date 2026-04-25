from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from . import models
from .database import engine
from .routes import auth_routes, quiz_routes, session_routes, grading_routes, dashboard_routes, admin_routes

# Create database tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Quiz Platform API", version="2.0")

# CORS — allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all API routers
app.include_router(auth_routes.router)
app.include_router(quiz_routes.router)
app.include_router(session_routes.router)
app.include_router(grading_routes.router)
app.include_router(dashboard_routes.router)
app.include_router(admin_routes.router)

# Mount static files for both apps
app.mount("/admin/static", StaticFiles(directory="quiz-admin/static"), name="admin-static")
app.mount("/static", StaticFiles(directory="quiz-user/static"), name="user-static")

# ──────────────────────────────────────────
# Admin Pages (quiz-admin/)
# ──────────────────────────────────────────
ADMIN_DIR = "quiz-admin"

@app.get("/setup")
async def serve_setup():
    return FileResponse(os.path.join(ADMIN_DIR, "setup.html"))

@app.get("/admin")
async def serve_admin_dashboard():
    return FileResponse(os.path.join(ADMIN_DIR, "admin-dashboard.html"))

@app.get("/admin/quiz-builder")
async def serve_quiz_builder():
    return FileResponse(os.path.join(ADMIN_DIR, "quiz-builder.html"))

@app.get("/admin/quiz-builder/{quiz_id}")
async def serve_quiz_editor(quiz_id: int):
    return FileResponse(os.path.join(ADMIN_DIR, "quiz-builder.html"))

@app.get("/admin/analytics/{quiz_id}")
async def serve_admin_analytics(quiz_id: int):
    return FileResponse(os.path.join(ADMIN_DIR, "admin-analytics.html"))

# ──────────────────────────────────────────
# User Pages (quiz-user/)
# ──────────────────────────────────────────
USER_DIR = "quiz-user"

@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(USER_DIR, "login.html"))

@app.get("/login")
async def serve_login():
    return FileResponse(os.path.join(USER_DIR, "login.html"))

@app.get("/register")
async def serve_register():
    return FileResponse(os.path.join(USER_DIR, "register.html"))

@app.get("/quiz/{share_token}")
async def serve_quiz_landing(share_token: str):
    return FileResponse(os.path.join(USER_DIR, "quiz-landing.html"))

@app.get("/quiz/{share_token}/session")
async def serve_quiz_session(share_token: str):
    return FileResponse(os.path.join(USER_DIR, "quiz-session.html"))

@app.get("/results/{submission_id}")
async def serve_results(submission_id: int):
    return FileResponse(os.path.join(USER_DIR, "results.html"))

@app.get("/leaderboard/{quiz_id}")
async def serve_leaderboard(quiz_id: int):
    return FileResponse(os.path.join(USER_DIR, "leaderboard.html"))

@app.get("/dashboard")
async def serve_student_dashboard():
    return FileResponse(os.path.join(USER_DIR, "student-dashboard.html"))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
