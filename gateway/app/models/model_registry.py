from sqlalchemy import Float, Integer, String
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class Model(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "models"

    name: Mapped[str] = mapped_column(String(255), unique=True)
    version: Mapped[str] = mapped_column(String(50), default="1.0")
    backend: Mapped[str] = mapped_column(String(50))  # vllm, llama-cpp
    file_path: Mapped[str] = mapped_column(String(1000))
    quantization: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parameters: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="available")  # downloading, available, loaded, error


class ModelEvaluation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "model_evaluations"

    model_name: Mapped[str] = mapped_column(String(255), index=True)
    benchmark: Mapped[str] = mapped_column(String(255))
    score: Mapped[float] = mapped_column(Float)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
