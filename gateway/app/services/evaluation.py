"""Evaluation Service — Phase 7.

Built-in benchmarks for model evaluation, comparison, and A/B testing.
All benchmark test sets are small and shipped inline (no external downloads).
"""

from __future__ import annotations

import json
import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_registry import ModelEvaluation
from app.models.training import ABTest
from app.services.llm import llm_backend

logger = logging.getLogger(__name__)


# =========================================================================
# Built-in benchmark test sets (small, air-gap-safe)
# =========================================================================

GENERAL_KNOWLEDGE_QUESTIONS = [
    {
        "question": "What is the chemical symbol for gold?",
        "choices": ["Au", "Ag", "Fe", "Cu"],
        "answer": "Au",
    },
    {
        "question": "Which planet is closest to the Sun?",
        "choices": ["Venus", "Mercury", "Mars", "Earth"],
        "answer": "Mercury",
    },
    {
        "question": "What year did World War II end?",
        "choices": ["1943", "1944", "1945", "1946"],
        "answer": "1945",
    },
    {
        "question": "What is the largest organ in the human body?",
        "choices": ["Heart", "Liver", "Skin", "Brain"],
        "answer": "Skin",
    },
    {
        "question": "What is the speed of light approximately in km/s?",
        "choices": ["150,000", "300,000", "500,000", "1,000,000"],
        "answer": "300,000",
    },
    {
        "question": "Which element has atomic number 1?",
        "choices": ["Helium", "Hydrogen", "Lithium", "Carbon"],
        "answer": "Hydrogen",
    },
    {
        "question": "What is the capital of Australia?",
        "choices": ["Sydney", "Melbourne", "Canberra", "Brisbane"],
        "answer": "Canberra",
    },
    {
        "question": "Who wrote 'Romeo and Juliet'?",
        "choices": ["Charles Dickens", "William Shakespeare", "Jane Austen", "Mark Twain"],
        "answer": "William Shakespeare",
    },
    {
        "question": "What is the boiling point of water in Celsius?",
        "choices": ["90", "100", "110", "120"],
        "answer": "100",
    },
    {
        "question": "How many chromosomes do humans have?",
        "choices": ["23", "44", "46", "48"],
        "answer": "46",
    },
]

CODE_GENERATION_PROBLEMS = [
    {
        "prompt": "Write a Python function called `add` that takes two numbers and returns their sum.",
        "test_input": "add(2, 3)",
        "expected": "5",
        "function_name": "add",
    },
    {
        "prompt": "Write a Python function called `is_palindrome` that takes a string and returns True if it is a palindrome (same forwards and backwards), False otherwise.",
        "test_input": "is_palindrome('racecar')",
        "expected": "True",
        "function_name": "is_palindrome",
    },
    {
        "prompt": "Write a Python function called `factorial` that computes the factorial of a non-negative integer n.",
        "test_input": "factorial(5)",
        "expected": "120",
        "function_name": "factorial",
    },
    {
        "prompt": "Write a Python function called `reverse_string` that takes a string and returns it reversed.",
        "test_input": "reverse_string('hello')",
        "expected": "'olleh'",
        "function_name": "reverse_string",
    },
    {
        "prompt": "Write a Python function called `fibonacci` that returns the nth Fibonacci number (0-indexed, fib(0)=0, fib(1)=1).",
        "test_input": "fibonacci(6)",
        "expected": "8",
        "function_name": "fibonacci",
    },
]

INSTRUCTION_FOLLOWING_TESTS = [
    {
        "instruction": "List exactly 3 colors. Respond with only the colors, one per line, no numbering.",
        "description": "List exactly 3 items",
        "check_type": "line_count_3",
    },
    {
        "instruction": "Respond with exactly one word: the opposite of 'hot'.",
        "description": "Single word response",
        "check_type": "single_word_cold",
    },
    {
        "instruction": "Write a sentence that contains exactly 5 words.",
        "description": "Exact word count",
        "check_type": "word_count_5",
    },
    {
        "instruction": "Reply with a JSON object containing keys 'name' and 'age'. Use any values.",
        "description": "JSON format output",
        "check_type": "json_name_age",
    },
    {
        "instruction": "Write the numbers 1 through 5, separated by commas, with no spaces.",
        "description": "Specific format constraint",
        "check_type": "comma_numbers",
    },
]

TOOL_CALLING_TESTS = [
    {
        "prompt": "What is the weather like in New York today?",
        "expected_tool": "get_weather",
        "description": "Weather query should trigger weather tool",
    },
    {
        "prompt": "Search our documents for information about quarterly revenue.",
        "expected_tool": "rag_search",
        "description": "Document search should trigger RAG tool",
    },
    {
        "prompt": "Calculate the square root of 144.",
        "expected_tool": "calculator",
        "description": "Math query should trigger calculator tool",
    },
    {
        "prompt": "Run this Python code: print('hello')",
        "expected_tool": "python_exec",
        "description": "Code execution request should trigger python tool",
    },
    {
        "prompt": "Read the file at /tmp/data.txt",
        "expected_tool": "file_read",
        "description": "File read request should trigger file_read tool",
    },
]

RAG_ACCURACY_TESTS = [
    {
        "context": "The Sovereign AI Hub is a locally-run, air-gapped AI platform. It uses PostgreSQL for data storage, Qdrant for vector search, and Redis for message queuing.",
        "question": "What vector database does the Sovereign AI Hub use?",
        "expected": "Qdrant",
    },
    {
        "context": "LoRA (Low-Rank Adaptation) is a technique for fine-tuning large language models by adding small trainable matrices to the model's attention layers, significantly reducing memory requirements.",
        "question": "What does LoRA stand for?",
        "expected": "Low-Rank Adaptation",
    },
    {
        "context": "The gateway service runs on port 8888, vLLM on port 8000, and llama.cpp on port 8080. The frontend runs on port 3000.",
        "question": "What port does vLLM run on?",
        "expected": "8000",
    },
    {
        "context": "GGUF is a file format for storing quantized language models. It was designed as a successor to GGML and is used by llama.cpp for inference.",
        "question": "What inference engine uses the GGUF format?",
        "expected": "llama.cpp",
    },
    {
        "context": "The platform supports two LLM backends: vLLM for GPU inference and llama.cpp for CPU inference. Both expose OpenAI-compatible APIs.",
        "question": "Which backend is used for CPU inference?",
        "expected": "llama.cpp",
    },
]


def _is_valid_json_with_keys(text: str, required_keys: list[str]) -> bool:
    """Check if text contains valid JSON with required keys."""
    # Try direct parse
    try:
        obj = json.loads(text.strip())
        return all(k in obj for k in required_keys)
    except json.JSONDecodeError:
        pass
    # Try markdown code blocks
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(1).strip())
            return all(k in obj for k in required_keys)
        except json.JSONDecodeError:
            pass
    # Try any JSON-like object
    match = re.search(r"\{[^}]+\}", text)
    if match:
        try:
            obj = json.loads(match.group())
            return all(k in obj for k in required_keys)
        except json.JSONDecodeError:
            pass
    return False


def _check_instruction(check_type: str, resp: str) -> bool:
    """Run a serializable instruction-following check."""
    if check_type == "line_count_3":
        return len([ln for ln in resp.strip().split("\n") if ln.strip()]) == 3
    if check_type == "single_word_cold":
        return len(resp.strip().split()) == 1 and "cold" in resp.strip().lower()
    if check_type == "word_count_5":
        return len(resp.strip().split()) == 5
    if check_type == "json_name_age":
        return _is_valid_json_with_keys(resp, ["name", "age"])
    if check_type == "comma_numbers":
        return "1,2,3,4,5" in resp.strip().replace(" ", "")
    return False


# =========================================================================
# Benchmark runners
# =========================================================================

async def _run_general_knowledge(model_name: str) -> dict:
    """Run MMLU-style multiple choice questions."""
    correct = 0
    total = len(GENERAL_KNOWLEDGE_QUESTIONS)
    details: list[dict] = []

    for q in GENERAL_KNOWLEDGE_QUESTIONS:
        choices_text = "\n".join(
            f"  {chr(65+i)}. {c}" for i, c in enumerate(q["choices"])
        )
        prompt = (
            f"Answer the following multiple choice question. "
            f"Reply with ONLY the letter (A, B, C, or D) of the correct answer.\n\n"
            f"Question: {q['question']}\n{choices_text}\n\nAnswer:"
        )

        try:
            response = await llm_backend.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                max_tokens=10,
                temperature=0.0,
            )
            answer_text = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            answer_letter = answer_text[0].upper() if answer_text else ""
            answer_idx = ord(answer_letter) - 65 if answer_letter in "ABCD" else -1
            chosen = (
                q["choices"][answer_idx]
                if 0 <= answer_idx < len(q["choices"])
                else ""
            )
            is_correct = chosen == q["answer"]
            if is_correct:
                correct += 1
            details.append({
                "question": q["question"],
                "expected": q["answer"],
                "got": chosen,
                "correct": is_correct,
            })
        except Exception as e:
            details.append({
                "question": q["question"],
                "expected": q["answer"],
                "got": f"ERROR: {e}",
                "correct": False,
            })

    return {
        "score": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "details": details,
    }


async def _run_code_generation(model_name: str) -> dict:
    """Run HumanEval-style code generation tests."""
    correct = 0
    total = len(CODE_GENERATION_PROBLEMS)
    details: list[dict] = []

    for problem in CODE_GENERATION_PROBLEMS:
        prompt = (
            f"{problem['prompt']}\n\n"
            f"Write only the Python function, no explanation. "
            f"Do not include any markdown formatting or code blocks."
        )

        try:
            response = await llm_backend.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                max_tokens=300,
                temperature=0.0,
            )
            code = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            # Clean up markdown code blocks if present
            code = re.sub(r"```python\s*\n?", "", code)
            code = re.sub(r"```\s*\n?", "", code)
            code = code.strip()

            # Verify by evaluating in a restricted namespace
            is_correct = False
            try:
                local_ns: dict = {}
                compiled = compile(code, "<benchmark>", "exec")
                allowed_builtins = {
                    "range": range, "len": len, "int": int, "float": float,
                    "str": str, "bool": bool, "list": list, "dict": dict,
                    "True": True, "False": False, "None": None,
                    "abs": abs, "min": min, "max": max, "sum": sum,
                    "isinstance": isinstance, "enumerate": enumerate,
                    "reversed": reversed, "sorted": sorted, "zip": zip,
                }
                sandbox_globals = {"__builtins__": allowed_builtins}
                eval(compiled, sandbox_globals, local_ns)  # noqa: S307
                result = eval(  # noqa: S307
                    problem["test_input"], sandbox_globals, local_ns
                )
                is_correct = (
                    str(result) == problem["expected"]
                    or repr(result) == problem["expected"]
                )
            except Exception:
                pass

            if is_correct:
                correct += 1
            details.append({
                "problem": problem["prompt"],
                "expected": problem["expected"],
                "code_generated": code[:200],
                "correct": is_correct,
            })
        except Exception as e:
            details.append({
                "problem": problem["prompt"],
                "expected": problem["expected"],
                "code_generated": f"ERROR: {e}",
                "correct": False,
            })

    return {
        "score": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "details": details,
    }


async def _run_instruction_following(model_name: str) -> dict:
    """Test adherence to specific formatting/constraint instructions."""
    correct = 0
    total = len(INSTRUCTION_FOLLOWING_TESTS)
    details: list[dict] = []

    for test in INSTRUCTION_FOLLOWING_TESTS:
        try:
            response = await llm_backend.chat_completion(
                messages=[{"role": "user", "content": test["instruction"]}],
                model=model_name,
                max_tokens=200,
                temperature=0.0,
            )
            answer = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            is_correct = _check_instruction(test["check_type"], answer)
            if is_correct:
                correct += 1
            details.append({
                "test": test["description"],
                "instruction": test["instruction"],
                "response": answer[:200],
                "passed": is_correct,
            })
        except Exception as e:
            details.append({
                "test": test["description"],
                "instruction": test["instruction"],
                "response": f"ERROR: {e}",
                "passed": False,
            })

    return {
        "score": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "details": details,
    }


async def _run_tool_calling(model_name: str) -> dict:
    """Test if model correctly identifies when to call tools."""
    correct = 0
    total = len(TOOL_CALLING_TESTS)
    details: list[dict] = []

    tools_description = (
        "Available tools:\n"
        "- get_weather(location): Get current weather for a location\n"
        "- rag_search(query): Search documents for information\n"
        "- calculator(expression): Evaluate a math expression\n"
        "- python_exec(code): Run Python code\n"
        "- file_read(path): Read a file from disk\n"
    )

    for test in TOOL_CALLING_TESTS:
        prompt = (
            f"{tools_description}\n"
            f"Given this user request, which tool should be called? "
            f"Reply with ONLY the tool name, nothing else.\n\n"
            f"User: {test['prompt']}\n\nTool:"
        )

        try:
            response = await llm_backend.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                max_tokens=30,
                temperature=0.0,
            )
            answer = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
                .lower()
            )
            is_correct = test["expected_tool"].lower() in answer
            if is_correct:
                correct += 1
            details.append({
                "test": test["description"],
                "expected_tool": test["expected_tool"],
                "got": answer[:100],
                "correct": is_correct,
            })
        except Exception as e:
            details.append({
                "test": test["description"],
                "expected_tool": test["expected_tool"],
                "got": f"ERROR: {e}",
                "correct": False,
            })

    return {
        "score": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "details": details,
    }


async def _run_rag_accuracy(model_name: str) -> dict:
    """Test retrieval quality with known context-question-answer triples."""
    correct = 0
    total = len(RAG_ACCURACY_TESTS)
    details: list[dict] = []

    for test in RAG_ACCURACY_TESTS:
        prompt = (
            f"Based on the following context, answer the question. "
            f"Be concise and specific.\n\n"
            f"Context: {test['context']}\n\n"
            f"Question: {test['question']}\n\nAnswer:"
        )

        try:
            response = await llm_backend.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                max_tokens=100,
                temperature=0.0,
            )
            answer = (
                response.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
                .strip()
            )
            is_correct = test["expected"].lower() in answer.lower()
            if is_correct:
                correct += 1
            details.append({
                "question": test["question"],
                "expected": test["expected"],
                "got": answer[:200],
                "correct": is_correct,
            })
        except Exception as e:
            details.append({
                "question": test["question"],
                "expected": test["expected"],
                "got": f"ERROR: {e}",
                "correct": False,
            })

    return {
        "score": correct / total if total > 0 else 0.0,
        "correct": correct,
        "total": total,
        "details": details,
    }


_BENCHMARK_RUNNERS = {
    "general_knowledge": _run_general_knowledge,
    "code_generation": _run_code_generation,
    "instruction_following": _run_instruction_following,
    "tool_calling": _run_tool_calling,
    "rag_accuracy": _run_rag_accuracy,
}


# =========================================================================
# Public API
# =========================================================================

async def run_benchmark(
    db: AsyncSession,
    model_name: str,
    benchmark_name: str,
) -> ModelEvaluation:
    """Run a specific benchmark against a model and store results."""
    runner = _BENCHMARK_RUNNERS.get(benchmark_name)
    if runner is None:
        raise ValueError(f"Unknown benchmark: {benchmark_name}")

    logger.info("Running benchmark '%s' on model '%s'", benchmark_name, model_name)
    result = await runner(model_name)

    evaluation = ModelEvaluation(
        model_name=model_name,
        benchmark=benchmark_name,
        score=result["score"],
        details=result,
    )
    db.add(evaluation)
    await db.flush()
    await db.refresh(evaluation)

    logger.info(
        "Benchmark '%s' on '%s': score=%.2f (%d/%d)",
        benchmark_name,
        model_name,
        result["score"],
        result.get("correct", 0),
        result.get("total", 0),
    )
    return evaluation


async def list_evaluation_results(
    db: AsyncSession,
    model_name: str | None = None,
    benchmark: str | None = None,
) -> list[ModelEvaluation]:
    """List stored evaluation results with optional filtering."""
    stmt = select(ModelEvaluation).order_by(ModelEvaluation.created_at.desc())
    if model_name:
        stmt = stmt.where(ModelEvaluation.model_name == model_name)
    if benchmark:
        stmt = stmt.where(ModelEvaluation.benchmark == benchmark)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def compare_models(
    db: AsyncSession,
    model_a: str,
    model_b: str,
    benchmark_name: str,
) -> dict:
    """Run the same benchmark on two models and compare."""
    eval_a = await run_benchmark(db, model_a, benchmark_name)
    eval_b = await run_benchmark(db, model_b, benchmark_name)

    winner = model_a if eval_a.score > eval_b.score else (
        model_b if eval_b.score > eval_a.score else "tie"
    )

    return {
        "model_a": model_a,
        "model_b": model_b,
        "benchmark": benchmark_name,
        "score_a": eval_a.score,
        "score_b": eval_b.score,
        "details_a": eval_a.details,
        "details_b": eval_b.details,
        "winner": winner,
    }


# =========================================================================
# A/B Testing
# =========================================================================

async def create_ab_test(
    db: AsyncSession,
    user_id: uuid.UUID,
    model_a: str,
    model_b: str,
    traffic_split: float = 0.5,
) -> ABTest:
    """Create a new A/B test between two models."""
    test = ABTest(
        model_a=model_a,
        model_b=model_b,
        traffic_split=traffic_split,
        status="active",
        metrics={
            "total_requests": 0,
            "model_a_requests": 0,
            "model_b_requests": 0,
            "model_a_preferred": 0,
            "model_b_preferred": 0,
            "model_a_ratings": [],
            "model_b_ratings": [],
        },
        created_by=user_id,
    )
    db.add(test)
    await db.flush()
    await db.refresh(test)
    return test


async def get_ab_test(db: AsyncSession, test_id: uuid.UUID) -> ABTest | None:
    result = await db.execute(select(ABTest).where(ABTest.id == test_id))
    return result.scalar_one_or_none()


async def record_ab_vote(
    db: AsyncSession,
    test_id: uuid.UUID,
    preferred_model: str,
    rating: int | None = None,
) -> ABTest | None:
    """Record a user preference vote for an A/B test."""
    test = await get_ab_test(db, test_id)
    if test is None or test.status != "active":
        return None

    metrics = test.metrics or {}
    if preferred_model == "a":
        metrics["model_a_preferred"] = metrics.get("model_a_preferred", 0) + 1
        if rating is not None:
            metrics.setdefault("model_a_ratings", []).append(rating)
    else:
        metrics["model_b_preferred"] = metrics.get("model_b_preferred", 0) + 1
        if rating is not None:
            metrics.setdefault("model_b_ratings", []).append(rating)

    metrics["total_requests"] = metrics.get("total_requests", 0) + 1
    test.metrics = metrics
    await db.flush()
    await db.refresh(test)
    return test


async def get_ab_results(db: AsyncSession, test_id: uuid.UUID) -> dict:
    """Get computed A/B test results."""
    test = await get_ab_test(db, test_id)
    if test is None:
        return {}

    metrics = test.metrics or {}
    a_ratings = metrics.get("model_a_ratings", [])
    b_ratings = metrics.get("model_b_ratings", [])

    a_preferred = metrics.get("model_a_preferred", 0)
    b_preferred = metrics.get("model_b_preferred", 0)

    winner = None
    if a_preferred > b_preferred:
        winner = test.model_a
    elif b_preferred > a_preferred:
        winner = test.model_b

    return {
        "id": str(test.id),
        "model_a": test.model_a,
        "model_b": test.model_b,
        "total_requests": metrics.get("total_requests", 0),
        "model_a_requests": metrics.get("model_a_requests", 0),
        "model_b_requests": metrics.get("model_b_requests", 0),
        "model_a_preferred": a_preferred,
        "model_b_preferred": b_preferred,
        "model_a_avg_rating": (
            sum(a_ratings) / len(a_ratings) if a_ratings else None
        ),
        "model_b_avg_rating": (
            sum(b_ratings) / len(b_ratings) if b_ratings else None
        ),
        "winner": winner,
        "status": test.status,
    }
