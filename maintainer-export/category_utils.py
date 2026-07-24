"""Assign interview question categories per issue #498 format."""

from __future__ import annotations

import re

CATEGORY_ORDER: list[tuple[str, str]] = [
    ("overview", "What it does"),
    ("implementation", "Core implementation"),
    ("integration", "Integration"),
    ("failure", "Failure modes & edge cases"),
    ("performance", "Performance"),
    ("security", "Security"),
    ("tradeoff", "Architecture tradeoffs"),
]

_CATEGORY_KEYS = {key for key, _ in CATEGORY_ORDER}


def infer_category(question: str, answer: str = "") -> str:
    text = f"{question} {answer}".lower()
    if re.search(
        r"\b(why |trade-?off|differently|non-goal|vs\.|versus|monolith|starting over|philosophy)\b",
        text,
    ):
        return "tradeoff"
    if re.search(
        r"\b(security|auth|secret|ssrf|jwt|rate limit|trust boundary|harden|encrypt|"
        r"cookie|token|wallboard token|audit|role|permission)\b",
        text,
    ):
        return "security"
    if re.search(
        r"\b(slow|latency|performance|pool|index|cap|pagination|keyset|"
        r"windowing|throughput|cpu|memory|queue depth|pacing)\b",
        text,
    ):
        return "performance"
    if re.search(
        r"\b(fail|failure|stuck|recover|degrade|empty|stale|edge|error|429|"
        r"503|circuit|honest|orphan|race|incident|blank)\b",
        text,
    ):
        return "failure"
    if re.search(
        r"\b(integrat|interact|relate|flow|pivot|wire|bundle|middleware|"
        r"frontend|ui |drawer|tab |webhook|notif|sync with|pairs with)\b",
        text,
    ):
        return "integration"
    if re.search(
        r"\b(what is|what are|describe |name |purpose|role of|at a glance|"
        r"high level|provide|anchors|explain <code>)\b",
        text,
    ) or question.lower().startswith(("what ", "describe ", "name ", "how is ")):
        return "overview"
    return "implementation"


def ensure_categories(questions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for item in questions:
        row = dict(item)
        cat = row.get("category", "")
        if cat not in _CATEGORY_KEYS:
            row["category"] = infer_category(row["q"], row.get("a", ""))
        out.append(row)
    return out
