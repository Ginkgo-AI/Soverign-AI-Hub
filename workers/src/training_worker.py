"""Background training worker — Phase 7.

Listens to Redis Streams for LoRA/QLoRA training jobs.
Pipeline: load dataset -> tokenize -> train -> save adapter -> report metrics.

Uses unsloth (preferred) or PEFT+transformers as fallback.
"""

import json
import logging
import os
import sys
import time
import uuid

import redis

# ── Configuration ──────────────────────────────────────────────────────

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
STREAM_NAME = "training_jobs"
CONSUMER_GROUP = "training_workers"
CONSUMER_NAME = f"trainer-{os.getpid()}"

POSTGRES_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://sovereign:changeme_in_production@localhost:5432/sovereign_ai",
)

MODELS_DIR = os.environ.get("MODELS_DIR", "/models")
ADAPTERS_DIR = os.environ.get("ADAPTERS_DIR", "/models/adapters")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("training_worker")

# ── Lazy DB initialization ─────────────────────────────────────────────

_sqlalchemy_ready = False
_Session = None
_TrainingJob = None


def _init_sqlalchemy():
    global _sqlalchemy_ready, _Session, _TrainingJob
    if _sqlalchemy_ready:
        return

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(POSTGRES_URL, pool_pre_ping=True)

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gateway"))
    from app.models.training import TrainingJob

    _Session = sessionmaker(bind=engine)
    _TrainingJob = TrainingJob
    _sqlalchemy_ready = True


def _update_job_status(
    job_id: str,
    status: str,
    progress: float = 0.0,
    metrics: dict | None = None,
    output_path: str | None = None,
    error_message: str | None = None,
):
    """Update training job status in PostgreSQL."""
    _init_sqlalchemy()
    session = _Session()
    try:
        job = session.query(_TrainingJob).filter_by(id=uuid.UUID(job_id)).first()
        if job:
            job.status = status
            job.progress = progress
            if metrics:
                job.metrics = metrics
            if output_path:
                job.output_path = output_path
            if error_message:
                job.error_message = error_message
            if status == "running" and not job.started_at:
                from datetime import datetime, timezone
                job.started_at = datetime.now(timezone.utc)
            if status in ("completed", "failed", "cancelled"):
                from datetime import datetime, timezone
                job.completed_at = datetime.now(timezone.utc)
            session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to update job status for %s", job_id)
    finally:
        session.close()


def _report_progress(r: redis.Redis, job_id: str, progress: float, metrics: dict):
    """Report live progress via Redis for real-time UI updates."""
    try:
        data = {"progress": progress, "metrics": metrics}
        r.set(f"training_progress:{job_id}", json.dumps(data), ex=3600)
    except Exception:
        logger.warning("Failed to report progress for %s", job_id)


def _report_loss(r: redis.Redis, job_id: str, step: int, loss: float, lr: float):
    """Append a loss data point to Redis list."""
    try:
        entry = {"step": step, "loss": loss, "learning_rate": lr}
        r.rpush(f"training_loss:{job_id}", json.dumps(entry))
        r.expire(f"training_loss:{job_id}", 86400)  # 24h TTL
    except Exception:
        pass


def _is_cancelled(r: redis.Redis, job_id: str) -> bool:
    """Check if the job has been cancelled."""
    try:
        return r.get(f"training_cancel:{job_id}") is not None
    except Exception:
        return False


# ── Training implementation ────────────────────────────────────────────

def _try_unsloth_training(config: dict, job_id: str, r: redis.Redis) -> dict:
    """Attempt training with unsloth (preferred, faster)."""
    from unsloth import FastLanguageModel

    base_model = config["base_model"]
    dataset_path = config["dataset_path"]
    output_path = config.get("output_path", os.path.join(ADAPTERS_DIR, job_id))
    max_seq_length = config.get("max_seq_length", 2048)
    lora_rank = config.get("lora_rank", 16)
    lora_alpha = config.get("lora_alpha", 32)
    target_modules = config.get("target_modules", ["q_proj", "v_proj", "k_proj", "o_proj"])
    learning_rate = config.get("learning_rate", 2e-4)
    epochs = config.get("epochs", 3)
    batch_size = config.get("batch_size", 4)
    warmup_steps = config.get("warmup_steps", 10)
    grad_accum = config.get("gradient_accumulation_steps", 4)
    quantization = config.get("quantization", "4bit")

    load_in_4bit = quantization == "4bit"

    logger.info("Loading base model: %s (4bit=%s)", base_model, load_in_4bit)
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=max_seq_length,
        load_in_4bit=load_in_4bit,
    )

    logger.info("Applying LoRA: rank=%d, alpha=%d, modules=%s", lora_rank, lora_alpha, target_modules)
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=0.0,
        bias="none",
        use_gradient_checkpointing="unsloth",
    )

    # Load dataset
    from datasets import load_dataset

    logger.info("Loading dataset: %s", dataset_path)
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # Tokenize
    def _format_sample(sample):
        if "messages" in sample:
            text = tokenizer.apply_chat_template(sample["messages"], tokenize=False)
        else:
            instruction = sample.get("instruction", sample.get("prompt", ""))
            inp = sample.get("input", "")
            output = sample.get("output", sample.get("completion", ""))
            if inp:
                text = f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n{output}"
            else:
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
        return {"text": text}

    dataset = dataset.map(_format_sample)

    # Setup trainer
    from trl import SFTTrainer
    from transformers import TrainingArguments

    os.makedirs(output_path, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=output_path,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        warmup_steps=warmup_steps,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        fp16=True,
        logging_steps=1,
        save_strategy="epoch",
        report_to="none",
    )

    # Custom callback for progress reporting
    from transformers import TrainerCallback

    class ProgressCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and state.global_step > 0:
                loss = logs.get("loss", 0)
                lr = logs.get("learning_rate", 0)
                progress = state.global_step / state.max_steps if state.max_steps else 0
                _report_loss(r, job_id, state.global_step, loss, lr)
                _report_progress(r, job_id, progress, {
                    "step": state.global_step,
                    "total_steps": state.max_steps,
                    "epoch": state.epoch,
                    "loss": loss,
                    "learning_rate": lr,
                })
                _update_job_status(job_id, "running", progress=progress)

        def on_step_end(self, args, state, control, **kwargs):
            if _is_cancelled(r, job_id):
                control.should_training_stop = True

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        args=training_args,
        callbacks=[ProgressCallback()],
    )

    logger.info("Starting training: %d epochs, batch=%d, lr=%s", epochs, batch_size, learning_rate)
    train_result = trainer.train()

    # Save adapter
    logger.info("Saving adapter to %s", output_path)
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)

    # Gather final metrics
    metrics = {
        "train_loss": train_result.metrics.get("train_loss"),
        "train_runtime": train_result.metrics.get("train_runtime"),
        "train_samples_per_second": train_result.metrics.get("train_samples_per_second"),
        "total_steps": train_result.metrics.get("total_flos"),
    }

    return {"output_path": output_path, "metrics": metrics}


def _try_peft_training(config: dict, job_id: str, r: redis.Redis) -> dict:
    """Fallback training with PEFT + transformers."""
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        TrainerCallback,
        TrainingArguments,
    )
    from peft import LoraConfig, get_peft_model, TaskType
    from trl import SFTTrainer
    from datasets import load_dataset
    import torch

    base_model = config["base_model"]
    dataset_path = config["dataset_path"]
    output_path = config.get("output_path", os.path.join(ADAPTERS_DIR, job_id))
    max_seq_length = config.get("max_seq_length", 2048)
    lora_rank = config.get("lora_rank", 16)
    lora_alpha = config.get("lora_alpha", 32)
    target_modules = config.get("target_modules", ["q_proj", "v_proj", "k_proj", "o_proj"])
    learning_rate = config.get("learning_rate", 2e-4)
    epochs = config.get("epochs", 3)
    batch_size = config.get("batch_size", 4)
    warmup_steps = config.get("warmup_steps", 10)
    grad_accum = config.get("gradient_accumulation_steps", 4)
    quantization = config.get("quantization", "4bit")

    logger.info("Loading model with PEFT: %s", base_model)

    model_kwargs = {"torch_dtype": torch.float16, "device_map": "auto"}
    if quantization == "4bit":
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
        )
    elif quantization == "8bit":
        from transformers import BitsAndBytesConfig

        model_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)

    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(base_model, **model_kwargs)

    # Apply LoRA
    lora_config = LoraConfig(
        r=lora_rank,
        lora_alpha=lora_alpha,
        target_modules=target_modules,
        lora_dropout=0.05,
        bias="none",
        task_type=TaskType.CAUSAL_LM,
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Load dataset
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def _format_sample(sample):
        if "messages" in sample:
            try:
                text = tokenizer.apply_chat_template(sample["messages"], tokenize=False)
            except Exception:
                parts = [f"{m['role']}: {m['content']}" for m in sample["messages"]]
                text = "\n".join(parts)
        else:
            instruction = sample.get("instruction", sample.get("prompt", ""))
            inp = sample.get("input", "")
            output = sample.get("output", sample.get("completion", ""))
            if inp:
                text = f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n{output}"
            else:
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
        return {"text": text}

    dataset = dataset.map(_format_sample)

    os.makedirs(output_path, exist_ok=True)

    training_args = TrainingArguments(
        output_dir=output_path,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        warmup_steps=warmup_steps,
        num_train_epochs=epochs,
        learning_rate=learning_rate,
        fp16=True,
        logging_steps=1,
        save_strategy="epoch",
        report_to="none",
    )

    class ProgressCallback(TrainerCallback):
        def on_log(self, args, state, control, logs=None, **kwargs):
            if logs and state.global_step > 0:
                loss = logs.get("loss", 0)
                lr = logs.get("learning_rate", 0)
                progress = state.global_step / state.max_steps if state.max_steps else 0
                _report_loss(r, job_id, state.global_step, loss, lr)
                _report_progress(r, job_id, progress, {
                    "step": state.global_step,
                    "total_steps": state.max_steps,
                    "epoch": state.epoch,
                    "loss": loss,
                    "learning_rate": lr,
                })
                _update_job_status(job_id, "running", progress=progress)

        def on_step_end(self, args, state, control, **kwargs):
            if _is_cancelled(r, job_id):
                control.should_training_stop = True

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        args=training_args,
        callbacks=[ProgressCallback()],
    )

    train_result = trainer.train()

    # Save adapter
    model.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)

    metrics = {
        "train_loss": train_result.metrics.get("train_loss"),
        "train_runtime": train_result.metrics.get("train_runtime"),
        "train_samples_per_second": train_result.metrics.get("train_samples_per_second"),
    }

    return {"output_path": output_path, "metrics": metrics}


def _merge_adapter_with_base(base_model_path: str, adapter_path: str, output_path: str):
    """Merge a LoRA adapter with its base model."""
    logger.info("Merging adapter %s with base %s -> %s", adapter_path, base_model_path, output_path)

    try:
        from unsloth import FastLanguageModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=base_model_path, load_in_4bit=False
        )
        model = FastLanguageModel.get_peft_model(model)
        model.load_adapter(adapter_path)
        merged = model.merge_and_unload()
    except ImportError:
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        model = AutoModelForCausalLM.from_pretrained(base_model_path)
        model = PeftModel.from_pretrained(model, adapter_path)
        merged = model.merge_and_unload()
        tokenizer = AutoTokenizer.from_pretrained(base_model_path)

    os.makedirs(output_path, exist_ok=True)
    merged.save_pretrained(output_path)
    tokenizer.save_pretrained(output_path)
    logger.info("Adapter merged and saved to %s", output_path)


# ── Job processor ──────────────────────────────────────────────────────

def process_training_job(job_data: dict, r: redis.Redis) -> None:
    """Process a single training job."""
    # Check for special merge action
    if job_data.get("action") == "merge_adapter":
        _merge_adapter_with_base(
            job_data["base_model_path"],
            job_data["adapter_path"],
            job_data["output_path"],
        )
        return

    job_id = job_data.get("job_id")
    config = json.loads(job_data.get("config", "{}"))
    config["base_model"] = job_data.get("base_model", config.get("base_model", ""))
    config["dataset_path"] = job_data.get("dataset_path", config.get("dataset_path", ""))
    config["output_path"] = job_data.get("output_path", os.path.join(ADAPTERS_DIR, job_id))

    logger.info("Starting training job: %s (model: %s)", job_id, config["base_model"])
    _update_job_status(job_id, "running", progress=0.0)

    try:
        # Try unsloth first, fall back to PEFT
        try:
            result = _try_unsloth_training(config, job_id, r)
            logger.info("Training completed with unsloth for job %s", job_id)
        except ImportError:
            logger.info("Unsloth not available, falling back to PEFT for job %s", job_id)
            result = _try_peft_training(config, job_id, r)
            logger.info("Training completed with PEFT for job %s", job_id)

        # Check if cancelled during training
        if _is_cancelled(r, job_id):
            _update_job_status(job_id, "cancelled", progress=1.0)
            logger.info("Training job %s was cancelled", job_id)
            return

        # Success
        _update_job_status(
            job_id, "completed",
            progress=1.0,
            metrics=result.get("metrics"),
            output_path=result.get("output_path"),
        )

        # Read loss history from Redis and store in DB metrics
        try:
            loss_data = r.lrange(f"training_loss:{job_id}", 0, -1)
            if loss_data:
                loss_history = [json.loads(d) for d in loss_data]
                _init_sqlalchemy()
                session = _Session()
                try:
                    job = session.query(_TrainingJob).filter_by(id=uuid.UUID(job_id)).first()
                    if job:
                        current_metrics = job.metrics or {}
                        current_metrics["loss_history"] = loss_history
                        job.metrics = current_metrics
                        session.commit()
                except Exception:
                    session.rollback()
                finally:
                    session.close()
        except Exception:
            pass

    except Exception as e:
        logger.exception("Training job %s failed", job_id)
        _update_job_status(job_id, "failed", error_message=str(e))


# ── Redis consumer loop ───────────────────────────────────────────────

def main():
    logger.info("Training worker starting (PID: %d)", os.getpid())

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    # Wait for Redis
    while True:
        try:
            r.ping()
            break
        except redis.ConnectionError:
            logger.info("Waiting for Redis at %s:%d ...", REDIS_HOST, REDIS_PORT)
            time.sleep(2)

    # Create consumer group
    try:
        r.xgroup_create(STREAM_NAME, CONSUMER_GROUP, id="0", mkstream=True)
    except redis.ResponseError:
        pass  # Group already exists

    logger.info(
        "Listening on stream '%s' as '%s/%s'...",
        STREAM_NAME, CONSUMER_GROUP, CONSUMER_NAME,
    )

    while True:
        try:
            messages = r.xreadgroup(
                CONSUMER_GROUP,
                CONSUMER_NAME,
                {STREAM_NAME: ">"},
                count=1,
                block=5000,
            )

            if not messages:
                continue

            for stream, entries in messages:
                for msg_id, data in entries:
                    try:
                        job = json.loads(data.get("payload", "{}"))
                        process_training_job(job, r)
                        r.xack(STREAM_NAME, CONSUMER_GROUP, msg_id)
                    except Exception as e:
                        logger.exception("Error processing message %s: %s", msg_id, e)

        except KeyboardInterrupt:
            logger.info("Shutting down training worker...")
            break
        except Exception as e:
            logger.exception("Worker error: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
