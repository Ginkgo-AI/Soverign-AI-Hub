"""Dataset Preparation Service — Phase 7.

Handles validation, conversion, statistics, and creation of training datasets.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training import TrainingDataset

logger = logging.getLogger(__name__)

DATASETS_DIR = "/models/datasets"


# ---------------------------------------------------------------------------
# Format detection & validation
# ---------------------------------------------------------------------------

def _detect_jsonl_schema(lines: list[dict]) -> str:
    """Detect whether JSONL follows instruction or messages format."""
    if not lines:
        return "unknown"
    sample = lines[0]
    if "messages" in sample:
        return "messages"
    if "instruction" in sample:
        return "instruction"
    if "input" in sample and "output" in sample:
        return "instruction"
    if "prompt" in sample and "completion" in sample:
        return "instruction"
    return "unknown"


def _validate_instruction_format(sample: dict) -> list[str]:
    errors: list[str] = []
    if "instruction" not in sample and "prompt" not in sample:
        errors.append("Missing 'instruction' or 'prompt' field")
    if "output" not in sample and "completion" not in sample:
        errors.append("Missing 'output' or 'completion' field")
    return errors


def _validate_messages_format(sample: dict) -> list[str]:
    errors: list[str] = []
    messages = sample.get("messages", [])
    if not isinstance(messages, list):
        errors.append("'messages' should be a list")
        return errors
    for i, msg in enumerate(messages):
        if "role" not in msg:
            errors.append(f"Message {i} missing 'role'")
        if "content" not in msg:
            errors.append(f"Message {i} missing 'content'")
    return errors


async def validate_dataset(file_path: str) -> dict:
    """Validate a dataset file and return info about its format and quality.

    Returns dict with keys: valid, format, schema, sample_count, errors, warnings.
    """
    result = {
        "valid": True,
        "format": "unknown",
        "schema": "unknown",
        "sample_count": 0,
        "errors": [],
        "warnings": [],
        "fields": [],
    }

    p = Path(file_path)
    if not p.exists():
        result["valid"] = False
        result["errors"].append(f"File not found: {file_path}")
        return result

    ext = p.suffix.lower()

    if ext == ".jsonl":
        result["format"] = "jsonl"
        lines: list[dict] = []
        line_errors: list[str] = []

        with open(p, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    lines.append(obj)
                except json.JSONDecodeError as e:
                    line_errors.append(f"Line {i+1}: Invalid JSON — {e}")
                    if len(line_errors) > 10:
                        break

        if line_errors:
            result["valid"] = False
            result["errors"].extend(line_errors)
            return result

        result["sample_count"] = len(lines)
        if not lines:
            result["valid"] = False
            result["errors"].append("File is empty")
            return result

        schema = _detect_jsonl_schema(lines)
        result["schema"] = schema
        result["fields"] = list(lines[0].keys())

        # Validate first few samples
        for i, sample in enumerate(lines[:5]):
            if schema == "instruction":
                errs = _validate_instruction_format(sample)
            elif schema == "messages":
                errs = _validate_messages_format(sample)
            else:
                errs = []
                result["warnings"].append("Unknown schema — could not validate fields")
                break
            for e in errs:
                result["errors"].append(f"Sample {i+1}: {e}")

        if result["errors"]:
            result["valid"] = False

    elif ext == ".csv":
        result["format"] = "csv"
        try:
            with open(p, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            result["sample_count"] = len(rows)
            result["schema"] = "csv"
            if rows:
                result["fields"] = list(rows[0].keys())
        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"CSV parse error: {e}")

    else:
        result["valid"] = False
        result["errors"].append(f"Unsupported format: {ext}")

    return result


# ---------------------------------------------------------------------------
# Dataset statistics
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(1, len(text) // 4)


async def get_dataset_stats(file_path: str) -> dict:
    """Get token count distribution, sample count, and average length."""
    p = Path(file_path)
    if not p.exists():
        return {"error": "File not found"}

    token_lengths: list[int] = []
    ext = p.suffix.lower()

    if ext == ".jsonl":
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Compute total text length of this sample
                text_parts: list[str] = []
                if "messages" in obj:
                    for msg in obj["messages"]:
                        text_parts.append(msg.get("content", ""))
                else:
                    for key in ("instruction", "input", "output", "prompt", "completion"):
                        if key in obj:
                            text_parts.append(str(obj[key]))
                total_text = " ".join(text_parts)
                token_lengths.append(_estimate_tokens(total_text))

    elif ext == ".csv":
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                total_text = " ".join(str(v) for v in row.values())
                token_lengths.append(_estimate_tokens(total_text))

    if not token_lengths:
        return {"sample_count": 0, "avg_token_length": 0, "min_token_length": 0, "max_token_length": 0}

    # Build distribution buckets
    buckets = {"0-128": 0, "128-256": 0, "256-512": 0, "512-1024": 0, "1024-2048": 0, "2048+": 0}
    for tl in token_lengths:
        if tl < 128:
            buckets["0-128"] += 1
        elif tl < 256:
            buckets["128-256"] += 1
        elif tl < 512:
            buckets["256-512"] += 1
        elif tl < 1024:
            buckets["512-1024"] += 1
        elif tl < 2048:
            buckets["1024-2048"] += 1
        else:
            buckets["2048+"] += 1

    return {
        "sample_count": len(token_lengths),
        "avg_token_length": round(sum(token_lengths) / len(token_lengths), 1),
        "min_token_length": min(token_lengths),
        "max_token_length": max(token_lengths),
        "token_distribution": buckets,
    }


# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

async def convert_dataset(
    input_path: str,
    output_format: str = "jsonl",
    output_path: str | None = None,
) -> str:
    """Convert between formats (CSV->JSONL, conversation->instruction).

    Returns the output file path.
    """
    p = Path(input_path)
    ext = p.suffix.lower()

    if output_path is None:
        output_path = str(p.with_suffix(f".{output_format}"))

    if ext == ".csv" and output_format == "jsonl":
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        with open(output_path, "w", encoding="utf-8") as f:
            for row in rows:
                # Try to map CSV columns to instruction format
                entry: dict = {}
                cols = {k.lower(): k for k in row.keys()}
                if "instruction" in cols:
                    entry["instruction"] = row[cols["instruction"]]
                    entry["input"] = row.get(cols.get("input", ""), "")
                    entry["output"] = row.get(cols.get("output", ""), row.get(cols.get("response", ""), ""))
                else:
                    # Fallback: first col as instruction, last as output
                    keys = list(row.keys())
                    if len(keys) >= 2:
                        entry["instruction"] = row[keys[0]]
                        entry["input"] = ""
                        entry["output"] = row[keys[-1]]
                    else:
                        entry = row
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    elif ext == ".jsonl" and output_format == "jsonl":
        # Convert between instruction <-> messages format
        lines: list[dict] = []
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                lines.append(json.loads(line))

        if not lines:
            return output_path

        schema = _detect_jsonl_schema(lines)

        with open(output_path, "w", encoding="utf-8") as f:
            for obj in lines:
                if schema == "instruction":
                    # Convert instruction to messages
                    messages = [
                        {"role": "user", "content": obj.get("instruction", "") + ("\n" + obj.get("input", "")).rstrip()},
                        {"role": "assistant", "content": obj.get("output", obj.get("completion", ""))},
                    ]
                    f.write(json.dumps({"messages": messages}, ensure_ascii=False) + "\n")
                elif schema == "messages":
                    # Convert messages to instruction
                    msgs = obj.get("messages", [])
                    user_msg = next((m["content"] for m in msgs if m.get("role") == "user"), "")
                    asst_msg = next((m["content"] for m in msgs if m.get("role") == "assistant"), "")
                    entry = {"instruction": user_msg, "input": "", "output": asst_msg}
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                else:
                    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    else:
        raise ValueError(f"Unsupported conversion: {ext} -> {output_format}")

    return output_path


# ---------------------------------------------------------------------------
# Create from conversations
# ---------------------------------------------------------------------------

async def create_from_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_ids: list[uuid.UUID],
    name: str,
    output_format: str = "messages",
) -> TrainingDataset:
    """Export conversation history as training data."""
    from app.models.conversation import Conversation, Message

    os.makedirs(DATASETS_DIR, exist_ok=True)
    file_path = os.path.join(DATASETS_DIR, f"{uuid.uuid4()}.jsonl")

    sample_count = 0

    with open(file_path, "w", encoding="utf-8") as f:
        for conv_id in conversation_ids:
            # Load messages for this conversation
            result = await db.execute(
                select(Message)
                .where(Message.conversation_id == conv_id)
                .order_by(Message.created_at)
            )
            messages = result.scalars().all()
            if not messages:
                continue

            if output_format == "messages":
                msg_list = []
                for msg in messages:
                    msg_list.append({"role": msg.role, "content": msg.content})
                f.write(json.dumps({"messages": msg_list}, ensure_ascii=False) + "\n")
                sample_count += 1
            else:
                # instruction format: pair user/assistant messages
                pairs: list[tuple] = []
                current_user = None
                for msg in messages:
                    if msg.role == "user":
                        current_user = msg.content
                    elif msg.role == "assistant" and current_user:
                        pairs.append((current_user, msg.content))
                        current_user = None
                for user_msg, asst_msg in pairs:
                    entry = {"instruction": user_msg, "input": "", "output": asst_msg}
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    sample_count += 1

    dataset = TrainingDataset(
        user_id=user_id,
        name=name,
        format=output_format,
        file_path=file_path,
        sample_count=sample_count,
    )
    db.add(dataset)
    await db.flush()
    await db.refresh(dataset)
    return dataset


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

async def split_dataset(
    file_path: str, train_ratio: float = 0.9
) -> dict:
    """Create train/validation splits. Returns paths."""
    import random

    p = Path(file_path)
    with open(p, "r", encoding="utf-8") as f:
        lines = [l for l in f if l.strip()]

    random.shuffle(lines)
    split_idx = int(len(lines) * train_ratio)
    train_lines = lines[:split_idx]
    val_lines = lines[split_idx:]

    train_path = str(p.with_name(p.stem + "_train" + p.suffix))
    val_path = str(p.with_name(p.stem + "_val" + p.suffix))

    with open(train_path, "w", encoding="utf-8") as f:
        f.writelines(train_lines)
    with open(val_path, "w", encoding="utf-8") as f:
        f.writelines(val_lines)

    return {
        "train_path": train_path,
        "train_count": len(train_lines),
        "val_path": val_path,
        "val_count": len(val_lines),
    }


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_datasets(
    db: AsyncSession, user_id: uuid.UUID | None = None
) -> list[TrainingDataset]:
    stmt = select(TrainingDataset).order_by(TrainingDataset.created_at.desc())
    if user_id:
        stmt = stmt.where(TrainingDataset.user_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_dataset(db: AsyncSession, ds_id: uuid.UUID) -> TrainingDataset | None:
    result = await db.execute(
        select(TrainingDataset).where(TrainingDataset.id == ds_id)
    )
    return result.scalar_one_or_none()


async def delete_dataset(
    db: AsyncSession, ds_id: uuid.UUID, delete_file: bool = True
) -> bool:
    ds = await get_dataset(db, ds_id)
    if ds is None:
        return False
    if delete_file:
        try:
            Path(ds.file_path).unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to delete dataset file: %s", ds.file_path)
    await db.delete(ds)
    await db.flush()
    return True


async def preview_dataset(file_path: str, limit: int = 10) -> list[dict]:
    """Return first N samples from a dataset."""
    p = Path(file_path)
    if not p.exists():
        return []

    samples: list[dict] = []
    ext = p.suffix.lower()

    if ext == ".jsonl":
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    samples.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if len(samples) >= limit:
                    break
    elif ext == ".csv":
        with open(p, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                samples.append(dict(row))
                if len(samples) >= limit:
                    break

    return samples
