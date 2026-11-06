import re
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

VALID_STATES = {"created", "ready", "running", "succeeded", "failed", "deleted"}
SANDBOX_NAME_REGEX = re.compile(r"^sbx-[a-z0-9]{8,}$")


class RunCreate(BaseModel):
    run_id: str = Field(..., min_length=1)
    sandbox_name: str
    problem_id: str = Field(..., min_length=1)
    state: str
    execution_target: str

    @field_validator("execution_target")
    @classmethod
    def validate_execution_target(cls, v: str) -> str:
        if v != "celesto_sandbox":
            raise ValueError(f"Invalid execution_target: {v}. Must be exactly 'celesto_sandbox'.")
        return v

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        if v not in VALID_STATES:
            raise ValueError(f"Invalid state: {v}. Must be one of {sorted(VALID_STATES)}.")
        return v

    @field_validator("sandbox_name")
    @classmethod
    def validate_sandbox_name(cls, v: str) -> str:
        if not SANDBOX_NAME_REGEX.match(v):
            raise ValueError(
                f"Invalid sandbox_name: '{v}'. Must start with 'sbx-' followed by 8 or more lowercase alphanumeric characters."
            )
        return v


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    sandbox_name: str
    problem_id: str
    state: str
    execution_target: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
