"""Deterministic pre/post safety and impulse-cooldown rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from ..context import Context


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    blocked: bool
    message: str


class SafetyProvider(Protocol):
    def check(self, user_message: str, context: Context) -> SafetyDecision: ...


class RuleSafetyProvider:
    _BULK_PATTERN = re.compile(r"(?:囤|买|采购|stock|buy)[^\d]{0,12}(\d+)\s*(?:箱|case|carton)", re.IGNORECASE)
    _HIGH_VALUE_TERMS = ("茅台", "maotai", "陈年", "收藏")

    def check(self, user_message: str, context: Context) -> SafetyDecision:
        text = user_message.lower()
        if self._is_resale_bulk(user_message):
            message = "该请求涉及批量囤货转卖，已按安全策略拦截。" if context.lang == "zh" else "This request involves bulk stockpiling for resale and is blocked by safety policy."
            return SafetyDecision(True, message)
        if self._is_tight_budget_high_value(user_message, context):
            message = "预算较紧，建议先比较单价或选择小规格；如果现在确实需要，也由你决定。" if context.lang == "zh" else "Budget is tight; compare unit prices or choose a smaller size first if this is not the right time."
            return SafetyDecision(False, message)
        return SafetyDecision(False, "")

    @staticmethod
    def _is_resale_bulk(user_message: str) -> bool:
        resale = any(term in user_message.lower() for term in ("转卖", "倒卖", "resell", "resale"))
        if not resale:
            return False
        match = RuleSafetyProvider._BULK_PATTERN.search(user_message)
        return match is not None and int(match.group(1)) >= 2

    @staticmethod
    def _is_tight_budget_high_value(user_message: str, context: Context) -> bool:
        if context.budget_cents is None:
            return False
        return any(term in user_message.lower() for term in RuleSafetyProvider._HIGH_VALUE_TERMS) and any(
            term in user_message for term in ("买", "想要", "推荐", "buy", "want")
        )
