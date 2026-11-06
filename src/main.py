from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from src.database import Base, engine, get_db
from src.models import Run
from src.schemas import RunCreate, RunResponse


def init_db():
    Base.metadata.create_all(bind=engine)
    db = next(get_db())
    try:
        existing = db.query(Run).filter(Run.sandbox_name == "sbx-seeddemo1").first()
        if not existing:
            seed_run = Run(
                run_id="run-seeddemo001",
                sandbox_name="sbx-seeddemo1",
                problem_id="prob-hostile-grader",
                state="deleted",
                execution_target="celesto_sandbox",
            )
            db.add(seed_run)
            db.commit()
    finally:
        db.close()


init_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Celesto Run Ledger API", version="1.0.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Requirement 11: invalid execution_target, state, or sandbox_name returns 400
    errors_summary = []
    for err in exc.errors():
        errors_summary.append({
            "loc": err.get("loc"),
            "msg": str(err.get("msg")),
            "type": err.get("type"),
        })
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": errors_summary},
    )


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/runs", response_model=List[RunResponse])
def get_runs(db: Session = Depends(get_db)):
    runs = db.query(Run).order_by(Run.created_at.asc()).all()
    return [RunResponse(**run.to_dict()) for run in runs]


@app.post("/api/runs", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
def create_run(run_in: RunCreate, db: Session = Depends(get_db)):
    existing = db.query(Run).filter(
        (Run.run_id == run_in.run_id) | (Run.sandbox_name == run_in.sandbox_name)
    ).first()
    if existing:
        existing.problem_id = run_in.problem_id
        existing.state = run_in.state
        existing.execution_target = run_in.execution_target
        db.commit()
        db.refresh(existing)
        return RunResponse(**existing.to_dict())

    new_run = Run(
        run_id=run_in.run_id,
        sandbox_name=run_in.sandbox_name,
        problem_id=run_in.problem_id,
        state=run_in.state,
        execution_target=run_in.execution_target,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)
    return RunResponse(**new_run.to_dict())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8080, reload=False)
