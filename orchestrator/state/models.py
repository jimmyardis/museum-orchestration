from pydantic import BaseModel
from typing import Optional


class Persona(BaseModel):
    id: str
    name: str
    hall: Optional[str] = None
    status: str = "pending"
    vector_count: int = 0
    page_url: Optional[str] = None
    voice_id: Optional[str] = None
    last_updated: Optional[str] = None
    created_at: Optional[str] = None


class Job(BaseModel):
    id: str
    persona_id: Optional[str] = None
    agent_name: str
    status: str = "queued"
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_msg: Optional[str] = None
    output_json: Optional[str] = None
    created_at: Optional[str] = None


class AgentStats(BaseModel):
    agent_name: str
    status: str = "idle"
    last_run: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    current_job_id: Optional[str] = None


class TriggerRequest(BaseModel):
    force: bool = False


class TriggerResponse(BaseModel):
    job_batch_id: str
    persona_id: str
    agents: list[str]
    message: str
