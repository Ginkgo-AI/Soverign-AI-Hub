"""Pydantic schemas for Phase 7 — Model Management, Fine-Tuning, Datasets, Evaluation."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Model Registry
# ---------------------------------------------------------------------------

class ModelRegister(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    version: str = "1.0"
    backend: str = Field(..., pattern="^(vllm|llama-cpp)$")
    file_path: str = Field(..., min_length=1)
    quantization: str | None = None
    parameters: dict[str, Any] | None = None


class ModelUpdate(BaseModel):
    name: str | None = None
    version: str | None = None
    backend: str | None = None
    file_path: str | None = None
    quantization: str | None = None
    parameters: dict[str, Any] | None = None
    status: str | None = None


class ModelOut(BaseModel):
    id: uuid.UUID
    name: str
    version: str
    backend: str
    file_path: str
    quantization: str | None = None
    parameters: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ModelListOut(BaseModel):
    models: list[ModelOut]
    total: int


class ModelScanRequest(BaseModel):
    path: str = "/models"


class ModelScanResult(BaseModel):
    discovered: int
    registered: int
    models: list[ModelOut]


class ModelDownloadRequest(BaseModel):
    source: str = Field(
        ..., description="HuggingFace repo ID (e.g. 'TheBloke/Mistral-7B-GGUF') or local path"
    )
    filename: str | None = Field(
        None, description="Specific file to download from the repo (for GGUF repos)"
    )
    destination: str = "/models"


class ModelDownloadOut(BaseModel):
    model_id: uuid.UUID
    status: str
    message: str


# ---------------------------------------------------------------------------
# Training / Fine-Tuning
# ---------------------------------------------------------------------------

class TrainingConfig(BaseModel):
    base_model: str = Field(..., description="Name or path of the base model")
    dataset_id: uuid.UUID | None = None
    dataset_path: str | None = None
    output_dir: str = "/models/adapters"
    learning_rate: float = Field(default=2e-4, ge=1e-6, le=1.0)
    epochs: int = Field(default=3, ge=1, le=100)
    batch_size: int = Field(default=4, ge=1, le=256)
    lora_rank: int = Field(default=16, ge=1, le=256)
    lora_alpha: int = Field(default=32, ge=1, le=512)
    target_modules: list[str] = Field(
        default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"]
    )
    quantization: str = Field(default="4bit", pattern="^(4bit|8bit|none)$")
    max_seq_length: int = Field(default=2048, ge=128, le=32768)
    warmup_steps: int = Field(default=10, ge=0)
    gradient_accumulation_steps: int = Field(default=4, ge=1, le=64)
    preset: str | None = Field(
        None,
        description="Preset config: quick, standard, thorough",
        pattern="^(quick|standard|thorough)$",
    )


class TrainingProgress(BaseModel):
    job_id: uuid.UUID
    status: str
    progress: float
    current_epoch: int | None = None
    total_epochs: int | None = None
    current_step: int | None = None
    total_steps: int | None = None
    loss: float | None = None
    learning_rate: float | None = None
    eval_loss: float | None = None
    metrics: dict[str, Any] | None = None


class TrainingJobOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    base_model: str
    dataset_path: str
    config: dict[str, Any] | None = None
    status: str
    progress: float
    metrics: dict[str, Any] | None = None
    output_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class TrainingJobListOut(BaseModel):
    jobs: list[TrainingJobOut]
    total: int


class TrainingMetricsOut(BaseModel):
    job_id: uuid.UUID
    loss_history: list[dict[str, Any]] = Field(default_factory=list)
    eval_history: list[dict[str, Any]] = Field(default_factory=list)
    final_metrics: dict[str, Any] | None = None


class AdapterInfo(BaseModel):
    job_id: uuid.UUID
    base_model: str
    path: str
    created_at: datetime | None = None


class AdapterListOut(BaseModel):
    adapters: list[AdapterInfo]
    total: int


# ---------------------------------------------------------------------------
# Datasets
# ---------------------------------------------------------------------------

class DatasetUpload(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    format: str = Field(default="jsonl", pattern="^(jsonl|csv|alpaca)$")


class DatasetOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    format: str
    file_path: str
    sample_count: int
    token_stats: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetListOut(BaseModel):
    datasets: list[DatasetOut]
    total: int


class DatasetStats(BaseModel):
    sample_count: int
    avg_token_length: float
    min_token_length: int
    max_token_length: int
    token_distribution: dict[str, int] | None = None
    format_detected: str
    schema_fields: list[str]


class DatasetPreview(BaseModel):
    samples: list[dict[str, Any]]
    total: int


class DatasetFromConversationsRequest(BaseModel):
    conversation_ids: list[uuid.UUID]
    name: str = Field(..., min_length=1, max_length=255)
    format: str = Field(default="messages", pattern="^(messages|instruction)$")


# ---------------------------------------------------------------------------
# Evaluation / Benchmarks
# ---------------------------------------------------------------------------

class BenchmarkRequest(BaseModel):
    model_name: str
    benchmark: str = Field(
        ...,
        pattern="^(general_knowledge|code_generation|rag_accuracy|tool_calling|instruction_following)$",
    )


class BenchmarkResult(BaseModel):
    id: uuid.UUID
    model_name: str
    benchmark: str
    score: float
    details: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class BenchmarkResultListOut(BaseModel):
    results: list[BenchmarkResult]
    total: int


class BenchmarkComparison(BaseModel):
    model_a: str
    model_b: str
    benchmark: str
    score_a: float
    score_b: float
    details_a: dict[str, Any] | None = None
    details_b: dict[str, Any] | None = None
    winner: str


class CompareRequest(BaseModel):
    model_a: str
    model_b: str
    benchmark: str = Field(
        ...,
        pattern="^(general_knowledge|code_generation|rag_accuracy|tool_calling|instruction_following)$",
    )


# ---------------------------------------------------------------------------
# A/B Testing
# ---------------------------------------------------------------------------

class ABTestCreate(BaseModel):
    model_a: str
    model_b: str
    traffic_split: float = Field(default=0.5, ge=0.0, le=1.0)


class ABTestOut(BaseModel):
    id: uuid.UUID
    model_a: str
    model_b: str
    traffic_split: float
    status: str
    metrics: dict[str, Any] | None = None
    created_at: datetime
    created_by: uuid.UUID

    model_config = {"from_attributes": True}


class ABTestResult(BaseModel):
    id: uuid.UUID
    model_a: str
    model_b: str
    total_requests: int
    model_a_requests: int
    model_b_requests: int
    model_a_preferred: int
    model_b_preferred: int
    model_a_avg_rating: float | None = None
    model_b_avg_rating: float | None = None
    winner: str | None = None
    status: str


class ABTestVote(BaseModel):
    test_id: uuid.UUID
    preferred_model: str = Field(..., pattern="^(a|b)$")
    rating: int | None = Field(None, ge=1, le=5)
