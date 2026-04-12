"""Guardrails service: prompt injection detection, secret leak prevention, content filtering."""
import re
from typing import List, Tuple
from pydantic import BaseModel


class GuardrailResult(BaseModel):
    safe: bool
    violations: List[str] = []
    sanitized_content: str = ""


# ── Prompt Injection Detection ────────────────────────────

INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?(previous\s+)?(instructions|rules|constraints)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"pretend\s+(you\s+are|to\s+be)", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"override\s+(your|the|all)\s+(instructions|rules|guidelines)", re.IGNORECASE),
    re.compile(r"disregard\s+(your|the|all)\s+(instructions|rules|training)", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+(are|have\s+no)", re.IGNORECASE),
    re.compile(r"new\s+instructions?\s*:", re.IGNORECASE),
    re.compile(r"<\|system\|>", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+(your|the|previous)\s+instructions", re.IGNORECASE),
    re.compile(r"bypass\s+(your|the|all|safety)\s+(rules|filters|guidelines|restrictions)", re.IGNORECASE),
]


# ── Secret Leak Detection ─────────────────────────────────

SECRET_PATTERNS = [
    re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}"),
    re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}"),
    re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"),
    re.compile(r"(?:api[_-]?key|apikey|api[_-]?secret)\s*[=:]\s*['\"]?[A-Za-z0-9\-_]{20,}['\"]?", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----"),
    re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s]{10,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
]

SECRET_REPLACEMENTS = [
    (re.compile(r"(?:AKIA|ABIA|ACCA|ASIA)[0-9A-Z]{16}"), "[AWS_KEY_REDACTED]"),
    (re.compile(r"aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}"), "aws_secret_access_key=[REDACTED]"),
    (re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"), "[GITHUB_TOKEN_REDACTED]"),
    (re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END"), "[PRIVATE_KEY_REDACTED]"),
    (re.compile(r"(?:postgres|mysql|mongodb|redis)://[^\s]{10,}"), "[DB_URL_REDACTED]"),
    (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*"), "Bearer [REDACTED]"),
]


# ── Content Filtering ──────────────────────────────────────

FORBIDDEN_TOPICS = [
    re.compile(r"how\s+to\s+(?:make|build|create)\s+(?:a\s+)?(?:bomb|weapon|explosive)", re.IGNORECASE),
    re.compile(r"how\s+to\s+hack\s+", re.IGNORECASE),
    re.compile(r"exploit\s+vulnerability", re.IGNORECASE),
]


def check_prompt_injection(text: str) -> List[str]:
    violations = []
    for pattern in INJECTION_PATTERNS:
        if pattern.search(text):
            violations.append(f"prompt_injection: matched '{pattern.pattern}'")
    return violations


def check_secret_leak(text: str) -> Tuple[List[str], str]:
    violations = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            violations.append(f"secret_leak: matched '{pattern.pattern}'")
    sanitized = text
    for pattern, replacement in SECRET_REPLACEMENTS:
        sanitized = pattern.sub(replacement, sanitized)
    return violations, sanitized


def check_forbidden_content(text: str) -> List[str]:
    violations = []
    for pattern in FORBIDDEN_TOPICS:
        if pattern.search(text):
            violations.append(f"forbidden_content: matched '{pattern.pattern}'")
    return violations


def check_guardrails(text: str) -> GuardrailResult:
    violations = []
    sanitized = text

    inj = check_prompt_injection(text)
    violations.extend(inj)

    sec, sanitized = check_secret_leak(text)
    violations.extend(sec)

    forbid = check_forbidden_content(text)
    violations.extend(forbid)

    return GuardrailResult(
        safe=len(violations) == 0,
        violations=violations,
        sanitized_content=sanitized,
    )
