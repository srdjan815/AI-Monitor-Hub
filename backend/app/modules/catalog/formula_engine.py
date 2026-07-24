from __future__ import annotations

import ast
import operator
from collections.abc import Callable
from decimal import Decimal
from typing import Any, ClassVar


class FormulaError(ValueError):
    pass


class FormulaEngine:
    _binary: ClassVar[dict[type[ast.operator], Callable[[Any, Any], Any]]] = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv,
        ast.Mod: operator.mod,
        ast.Pow: operator.pow,
    }
    _unary: ClassVar[dict[type[ast.unaryop], Callable[[Any], Any]]] = {
        ast.UAdd: operator.pos,
        ast.USub: operator.neg,
    }
    _functions: ClassVar[dict[str, Callable[..., Any]]] = {
        "min": min,
        "max": max,
        "round": round,
        "abs": abs,
    }

    def dependencies(self, expression: str) -> set[str]:
        tree = self._parse(expression)
        return {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id not in self._functions
        }

    def evaluate(self, expression: str, values: dict[str, Any]) -> Decimal:
        tree = self._parse(expression)
        missing = self.dependencies(expression) - values.keys()
        if missing:
            raise FormulaError(f"Missing formula values: {', '.join(sorted(missing))}")
        result = self._eval(tree.body, values)
        try:
            return Decimal(str(result))
        except Exception as exc:
            raise FormulaError("Formula result is not numeric") from exc

    def validate_graph(self, graph: dict[str, set[str]]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visiting:
                raise FormulaError(f"Formula dependency cycle at {node}")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph.get(node, set()):
                if dependency in graph:
                    visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            visit(node)

    def _parse(self, expression: str) -> ast.Expression:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise FormulaError(f"Invalid formula: {exc.msg}") from exc
        allowed = (
            ast.Expression,
            ast.BinOp,
            ast.UnaryOp,
            ast.Constant,
            ast.Name,
            ast.Load,
            ast.Call,
            *self._binary,
            *self._unary,
        )
        for node in ast.walk(tree):
            if not isinstance(node, allowed):
                raise FormulaError(
                    f"Unsupported formula element: {type(node).__name__}"
                )
            if isinstance(node, ast.Call):
                if (
                    not isinstance(node.func, ast.Name)
                    or node.func.id not in self._functions
                    or node.keywords
                ):
                    raise FormulaError("Unsupported formula function")
        return tree

    def _eval(self, node: ast.AST, values: dict[str, Any]) -> Any:
        if isinstance(node, ast.Constant):
            if not isinstance(node.value, (int, float)):
                raise FormulaError("Only numeric constants are allowed")
            return node.value
        if isinstance(node, ast.Name):
            return values[node.id]
        if isinstance(node, ast.BinOp):
            left = self._eval(node.left, values)
            right = self._eval(node.right, values)
            if isinstance(node.op, ast.Pow) and abs(Decimal(str(right))) > 10:
                raise FormulaError("Exponent is outside the safe range")
            try:
                return self._binary[type(node.op)](left, right)
            except (ArithmeticError, OverflowError) as exc:
                raise FormulaError(f"Formula arithmetic failed: {exc}") from exc
        if isinstance(node, ast.UnaryOp):
            return self._unary[type(node.op)](self._eval(node.operand, values))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self._eval(arg, values) for arg in node.args]
            return self._functions[node.func.id](*args)
        raise FormulaError("Unsupported formula expression")
