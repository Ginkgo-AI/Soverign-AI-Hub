"""
Code Analysis Service -- static analysis, LLM-powered explanation, review,
documentation generation, and diff analysis.

Uses AST parsing for Python, regex-based patterns for other languages,
and the LLM backend for intelligent analysis tasks.
"""

from __future__ import annotations

import ast
import logging
import re
from typing import Any

from app.schemas.code import (
    AnalysisIssue,
    AnalyzeResponse,
    ReviewFinding,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static analysis: Python AST-based
# ---------------------------------------------------------------------------

def _analyze_python_ast(code: str) -> list[AnalysisIssue]:
    """Perform AST-based static analysis on Python code."""
    issues: list[AnalysisIssue] = []

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        issues.append(
            AnalysisIssue(
                line=e.lineno,
                column=e.offset,
                severity="error",
                message=f"Syntax error: {e.msg}",
                rule="syntax_error",
            )
        )
        return issues

    for node in ast.walk(tree):
        # Bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            issues.append(
                AnalysisIssue(
                    line=node.lineno,
                    severity="warning",
                    message="Bare except clause catches all exceptions including SystemExit and KeyboardInterrupt",
                    rule="bare_except",
                )
            )

        # Mutable default argument
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for default in node.args.defaults + node.args.kw_defaults:
                if default and isinstance(default, (ast.List, ast.Dict, ast.Set)):
                    issues.append(
                        AnalysisIssue(
                            line=node.lineno,
                            severity="warning",
                            message=f"Mutable default argument in function '{node.name}'",
                            rule="mutable_default",
                        )
                    )

            # Missing docstring
            if not (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)
            ):
                issues.append(
                    AnalysisIssue(
                        line=node.lineno,
                        severity="info",
                        message=f"Function '{node.name}' is missing a docstring",
                        rule="missing_docstring",
                    )
                )

        # Global statement
        if isinstance(node, ast.Global):
            issues.append(
                AnalysisIssue(
                    line=node.lineno,
                    severity="info",
                    message=f"Use of global statement for: {', '.join(node.names)}",
                    rule="global_statement",
                )
            )

        # Assert in non-test code (could be stripped with -O)
        if isinstance(node, ast.Assert):
            issues.append(
                AnalysisIssue(
                    line=node.lineno,
                    severity="info",
                    message="Assert statements are removed when Python runs with -O flag",
                    rule="assert_usage",
                )
            )

        # eval/exec usage
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ("eval", "exec"):
                issues.append(
                    AnalysisIssue(
                        line=node.lineno,
                        severity="error",
                        message=f"Use of {node.func.id}() is a security risk",
                        rule="dangerous_function",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Static analysis: Regex-based patterns (multi-language)
# ---------------------------------------------------------------------------

_SECURITY_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"password\s*=\s*['\"]", re.IGNORECASE),
        "message": "Possible hardcoded password detected",
        "severity": "error",
        "rule": "hardcoded_password",
        "languages": None,  # all
    },
    {
        "pattern": re.compile(r"api[_-]?key\s*=\s*['\"]", re.IGNORECASE),
        "message": "Possible hardcoded API key detected",
        "severity": "error",
        "rule": "hardcoded_api_key",
        "languages": None,
    },
    {
        "pattern": re.compile(r"TODO|FIXME|HACK|XXX", re.IGNORECASE),
        "message": "TODO/FIXME comment found",
        "severity": "info",
        "rule": "todo_comment",
        "languages": None,
    },
    {
        "pattern": re.compile(r"console\.log\(", re.IGNORECASE),
        "message": "console.log() call found (remove for production)",
        "severity": "info",
        "rule": "console_log",
        "languages": ["javascript", "typescript"],
    },
    {
        "pattern": re.compile(r"print\(", re.IGNORECASE),
        "message": "print() call found (consider using logging)",
        "severity": "info",
        "rule": "print_statement",
        "languages": ["python"],
    },
    {
        "pattern": re.compile(r"\.innerHTML\s*=", re.IGNORECASE),
        "message": "Direct innerHTML assignment -- potential XSS vulnerability",
        "severity": "error",
        "rule": "xss_innerhtml",
        "languages": ["javascript", "typescript"],
    },
    {
        "pattern": re.compile(r"SELECT\s+.*\+.*FROM", re.IGNORECASE),
        "message": "Possible SQL injection (string concatenation in query)",
        "severity": "error",
        "rule": "sql_injection",
        "languages": None,
    },
]


def _analyze_regex(code: str, language: str) -> list[AnalysisIssue]:
    """Regex-based pattern analysis for common issues."""
    issues: list[AnalysisIssue] = []
    lines = code.splitlines()

    for i, line in enumerate(lines, start=1):
        for pat in _SECURITY_PATTERNS:
            if pat["languages"] and language not in pat["languages"]:
                continue
            if pat["pattern"].search(line):
                issues.append(
                    AnalysisIssue(
                        line=i,
                        severity=pat["severity"],
                        message=pat["message"],
                        rule=pat["rule"],
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Public static analysis API
# ---------------------------------------------------------------------------

def analyze_code(
    code: str,
    language: str = "python",
    analysis_type: str = "full",
) -> AnalyzeResponse:
    """
    Perform static analysis on code.

    analysis_type: full, security, bugs, style
    """
    issues: list[AnalysisIssue] = []

    if language == "python" and analysis_type in ("full", "bugs", "style"):
        issues.extend(_analyze_python_ast(code))

    if analysis_type in ("full", "security"):
        issues.extend(_analyze_regex(code, language))

    # Sort by severity then line number
    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda x: (severity_order.get(x.severity, 3), x.line or 0))

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    summary = f"Found {len(issues)} issue(s): {error_count} error(s), {warning_count} warning(s), {info_count} info"

    return AnalyzeResponse(
        issues=issues,
        summary=summary,
        issue_count=len(issues),
        language=language,
    )


# ---------------------------------------------------------------------------
# Diff analysis
# ---------------------------------------------------------------------------

def parse_unified_diff(diff: str) -> dict[str, Any]:
    """
    Parse a unified diff and return structured info.
    """
    files: list[dict[str, Any]] = []
    current_file: dict[str, Any] | None = None
    additions = 0
    deletions = 0

    for line in diff.splitlines():
        if line.startswith("diff --git"):
            if current_file:
                files.append(current_file)
            # Extract filename
            parts = line.split(" b/")
            fname = parts[-1] if len(parts) > 1 else "unknown"
            current_file = {"file": fname, "additions": 0, "deletions": 0, "changes": []}
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
            if current_file:
                current_file["additions"] += 1
                current_file["changes"].append(line)
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
            if current_file:
                current_file["deletions"] += 1
                current_file["changes"].append(line)

    if current_file:
        files.append(current_file)

    return {
        "files_changed": len(files),
        "additions": additions,
        "deletions": deletions,
        "files": files,
    }


# ---------------------------------------------------------------------------
# LLM-powered analysis functions
# ---------------------------------------------------------------------------

CODE_EXPLAIN_SYSTEM_PROMPT = """You are an expert code analyst. Explain the provided code clearly and concisely.
Focus on:
- What the code does (high-level purpose)
- How it works (key algorithms/patterns)
- Important details (edge cases, potential issues)
- Dependencies and side effects

Respond in well-structured markdown."""

CODE_REVIEW_SYSTEM_PROMPT = """You are an expert code reviewer. Review the provided code for:
- Bugs and logical errors
- Security vulnerabilities
- Performance issues
- Code style and readability
- Best practices

For each finding, provide:
- Severity (info/warning/error/critical)
- Category (bug, security, performance, style)
- Clear description of the issue
- Suggested fix

Format your review as a structured list of findings."""

CODE_GENERATE_SYSTEM_PROMPT = """You are an expert programmer. Generate clean, well-documented code based on the user's description.
- Follow best practices for the specified language
- Include appropriate error handling
- Add docstrings/comments where helpful
- Keep the code focused and minimal

Return ONLY the code wrapped in a code block with the language specified."""

COMMIT_MESSAGE_SYSTEM_PROMPT = """You are a developer generating a git commit message from a diff.
Follow the Conventional Commits format:
  type(scope): description

Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build
- Keep the subject line under 72 characters
- Add a body with details if the change is complex
- Focus on WHY, not just WHAT

Return the commit message only, no extra commentary."""

DIFF_SUMMARY_SYSTEM_PROMPT = """You are a developer summarizing code changes from a git diff.
Provide a clear, concise summary of:
- What changed and why (if apparent)
- Files modified
- Key additions and removals

Keep it brief but informative."""

DOCSTRING_SYSTEM_PROMPT = """You are an expert at writing documentation. Generate clear, complete docstrings
or documentation comments for the provided code. Use the conventional style for the language:
- Python: Google or NumPy style docstrings
- JavaScript/TypeScript: JSDoc
- Other languages: appropriate doc comment format

Return the code with documentation added."""


async def explain_code_with_llm(
    code: str,
    language: str = "python",
    detail_level: str = "normal",
) -> str:
    """Use LLM to explain code."""
    from app.services.llm import llm_backend

    detail_instruction = {
        "brief": "Keep your explanation very brief (2-3 sentences).",
        "normal": "Provide a clear explanation with moderate detail.",
        "detailed": "Provide a thorough, detailed explanation covering all aspects.",
    }.get(detail_level, "")

    messages = [
        {"role": "system", "content": CODE_EXPLAIN_SYSTEM_PROMPT + "\n" + detail_instruction},
        {"role": "user", "content": f"Language: {language}\n\n```{language}\n{code}\n```"},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.3)
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("LLM code explanation failed: %s", exc)
        return f"Code explanation unavailable: {exc}"


async def review_code_with_llm(
    code: str | None = None,
    diff: str | None = None,
    language: str = "python",
    focus: str = "general",
) -> str:
    """Use LLM to review code or a diff."""
    from app.services.llm import llm_backend

    content_parts = [f"Language: {language}", f"Review focus: {focus}"]
    if code:
        content_parts.append(f"```{language}\n{code}\n```")
    if diff:
        content_parts.append(f"Diff:\n```diff\n{diff}\n```")

    messages = [
        {"role": "system", "content": CODE_REVIEW_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.3)
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("LLM code review failed: %s", exc)
        return f"Code review unavailable: {exc}"


async def generate_code_with_llm(
    prompt: str,
    language: str = "python",
    context: str | None = None,
) -> dict[str, str]:
    """Use LLM to generate code from a description."""
    from app.services.llm import llm_backend

    content_parts = [f"Language: {language}", f"Task: {prompt}"]
    if context:
        content_parts.append(f"Context/existing code:\n```\n{context}\n```")

    messages = [
        {"role": "system", "content": CODE_GENERATE_SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(content_parts)},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.4)
        full_response = response["choices"][0]["message"]["content"]

        # Try to extract code block
        code_match = re.search(r"```[\w]*\n(.*?)```", full_response, re.DOTALL)
        if code_match:
            generated_code = code_match.group(1).strip()
            explanation = full_response.replace(code_match.group(0), "").strip()
        else:
            generated_code = full_response
            explanation = ""

        return {"code": generated_code, "explanation": explanation}
    except Exception as exc:
        logger.error("LLM code generation failed: %s", exc)
        return {"code": "", "explanation": f"Code generation unavailable: {exc}"}


async def generate_commit_message(diff: str, style: str = "conventional") -> dict[str, str]:
    """Use LLM to generate a commit message from a diff."""
    from app.services.llm import llm_backend

    messages = [
        {"role": "system", "content": COMMIT_MESSAGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"Style: {style}\n\nDiff:\n```diff\n{diff}\n```"},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.3)
        full_message = response["choices"][0]["message"]["content"].strip()

        # Split into subject and body
        parts = full_message.split("\n", 1)
        subject = parts[0].strip()
        body = parts[1].strip() if len(parts) > 1 else ""

        return {"message": full_message, "subject": subject, "body": body}
    except Exception as exc:
        logger.error("LLM commit message generation failed: %s", exc)
        return {
            "message": "chore: update code",
            "subject": "chore: update code",
            "body": f"(Auto-generated -- LLM unavailable: {exc})",
        }


async def summarize_diff(diff: str) -> dict[str, Any]:
    """Use LLM to summarize a diff, supplemented with parsed stats."""
    from app.services.llm import llm_backend

    parsed = parse_unified_diff(diff)

    messages = [
        {"role": "system", "content": DIFF_SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": f"```diff\n{diff[:8000]}\n```"},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.3)
        summary = response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("LLM diff summary failed: %s", exc)
        summary = f"Diff summary unavailable: {exc}"

    file_summaries = [
        {"file": f["file"], "changes": f"+{f['additions']}/-{f['deletions']}"}
        for f in parsed["files"]
    ]

    return {
        "summary": summary,
        "files_changed": parsed["files_changed"],
        "additions": parsed["additions"],
        "deletions": parsed["deletions"],
        "file_summaries": file_summaries,
    }


async def generate_docstrings(code: str, language: str = "python") -> str:
    """Use LLM to add documentation to code."""
    from app.services.llm import llm_backend

    messages = [
        {"role": "system", "content": DOCSTRING_SYSTEM_PROMPT},
        {"role": "user", "content": f"Language: {language}\n\n```{language}\n{code}\n```"},
    ]

    try:
        response = await llm_backend.chat_completion(messages=messages, temperature=0.3)
        return response["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.error("LLM docstring generation failed: %s", exc)
        return code  # Return original code if LLM fails
