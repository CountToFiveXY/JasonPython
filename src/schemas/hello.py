"""HTTP schemas for the hello workflow API."""

from pydantic import BaseModel


class WorkflowResponse(BaseModel):
    workflow_id: str
    result: str
