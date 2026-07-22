from app.modules.execution.enums import JobStatus
from app.modules.execution.schemas import JobCreate


def test_job_create_defaults() -> None:
    job = JobCreate(job_type="system.health_echo")
    assert job.queue == "default"
    assert job.priority == 100
    assert job.max_attempts == 3
    assert job.payload == {}


def test_job_status_values_are_stable() -> None:
    assert JobStatus.PENDING.value == "PENDING"
    assert JobStatus.DEAD_LETTER.value == "DEAD_LETTER"
