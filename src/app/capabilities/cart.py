"""Stateless cart capability backed by a configurable provider."""

from __future__ import annotations

from ..context import CartData, CartLine, Context
from ..providers.cart_stub import CartDomainError, CartProvider, CartRecord


class CartCapability:
    def __init__(self, provider: CartProvider) -> None:
        self._provider = provider

    async def execute(
        self,
        action: str,
        context: Context,
        product_ref: str | None = None,
        qty: int = 1,
    ) -> CartData:
        if action == "add" and not 1 <= qty <= 1000:
            raise ValueError("qty must be between 1 and 1000")
        if action == "add":
            if not product_ref:
                raise ValueError("product_ref is required for add")
            lines = await self._provider.add(context.user_ref, product_ref, qty)
            return self._data(lines, context, product_ref)
        if action == "remove":
            if not product_ref:
                raise ValueError("product_ref is required for remove")
            lines = await self._provider.remove(context.user_ref, product_ref)
            return self._data(lines, context)
        if action == "list":
            lines = await self._provider.list(context.user_ref)
            return self._data(lines, context)
        if action == "checkout":
            lines = await self._provider.list(context.user_ref)
            if not lines:
                raise CartDomainError("CART_EMPTY", "cart is empty")
            checked_out = self._data(lines, context)
            await self._provider.clear(context.user_ref)
            return checked_out
        raise ValueError("unsupported cart action")

    def _data(self, records: list[CartRecord], context: Context, added_product_ref: str | None = None) -> CartData:
        lines = [CartLine.model_validate(record.model_dump()) for record in records]
        lines.sort(key=lambda line: (
            line.unit_price_cents if line.unit_price_cents is not None else line.price_cents,
            line.product_ref,
        ))
        total = sum(line.price_cents * line.qty for line in lines)
        warnings: list[dict[str, str]] = []
        if context.budget_cents is not None and total > context.budget_cents:
            message = (
                f"购物车总额 {total / 100:.2f} {context.currency}，超出预算 {context.budget_cents / 100:.2f}。"
                if context.lang == "zh" else
                f"Cart total {total / 100:.2f} {context.currency} exceeds budget {context.budget_cents / 100:.2f}."
            )
            warnings.append({"code": "BUDGET_EXCEEDED_WARNING", "message": message})
        if added_product_ref and context.budget_cents is not None:
            record = next((line for line in records if line.product_ref == added_product_ref), None)
            item_total = record.price_cents * record.qty if record else 0
            if item_total > context.budget_cents and total <= context.budget_cents:
                if context.lang == "zh":
                    message = f"商品小计 {item_total / 100:.2f} {context.currency}，超出预算 {context.budget_cents / 100:.2f}。"
                else:
                    message = f"Item subtotal {item_total / 100:.2f} {context.currency} exceeds budget {context.budget_cents / 100:.2f}."
                warnings.append({"code": "BUDGET_EXCEEDED_WARNING", "message": message})
        return CartData(cart_lines=lines, cart_total_cents=total, warnings=warnings)
