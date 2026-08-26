from __future__ import annotations

from .lua_expr import emit_expr
from .semantic_ir import (
    Assign,
    Attribute,
    Branch,
    Call,
    CallExpr,
    Concat,
    Expr,
    Index,
    Jump,
    Name,
    Opaque,
    Return,
    SemanticProgram,
)
from .semantic_opt import stable_names
from .structure import (
    BlockRegion,
    IfRegion,
    Region,
    ReturnRegion,
    SequenceRegion,
    StateMachineRegion,
    WhileRegion,
)


def _rename_expr(expr: Expr, names: dict[str, str]) -> Expr:
    if isinstance(expr, Name):
        return Name(names.get(expr.name, expr.name))
    if isinstance(expr, Attribute):
        return Attribute(_rename_expr(expr.base, names), expr.name)
    if isinstance(expr, Index):
        return Index(_rename_expr(expr.base, names), _rename_expr(expr.key, names))
    if isinstance(expr, Concat):
        return Concat(tuple(_rename_expr(part, names) for part in expr.parts))
    if isinstance(expr, CallExpr):
        return CallExpr(
            _rename_expr(expr.callee, names),
            tuple(_rename_expr(arg, names) for arg in expr.args),
        )
    return expr


def _expr(expr: Expr, names: dict[str, str]) -> str:
    return emit_expr(_rename_expr(expr, names))


def _instruction_lines(
    instruction,
    names: dict[str, str],
    declared: set[str],
    indent: int,
    include_control: bool = False,
) -> list[str]:
    prefix = "    " * indent
    if isinstance(instruction, Assign):
        target = _rename_expr(instruction.target, names)
        value = _expr(instruction.value, names)
        if isinstance(target, Name):
            if target.name not in declared:
                declared.add(target.name)
                return [f"{prefix}local {target.name} = {value}"]
            return [f"{prefix}{target.name} = {value}"]
        return [f"{prefix}{emit_expr(target)} = {value}"]
    if isinstance(instruction, Call):
        return [f"{prefix}{_expr(instruction.value, names)}"]
    if isinstance(instruction, Opaque):
        return [f"{prefix}{instruction.source.strip()}"]
    if include_control and isinstance(instruction, Jump):
        return [f"{prefix}state = {instruction.target}"]
    if include_control and isinstance(instruction, Branch):
        condition = _expr(instruction.condition, names)
        return [
            f"{prefix}if {condition} then",
            f"{prefix}    state = {instruction.true_state}",
            f"{prefix}else",
            f"{prefix}    state = {instruction.false_state}",
            f"{prefix}end",
        ]
    if isinstance(instruction, Return):
        values = ", ".join(_expr(value, names) for value in instruction.values)
        return [f"{prefix}return{(' ' + values) if values else ''}"]
    return []


def _block_effects(
    program: SemanticProgram,
    state: int,
    names: dict[str, str],
    declared: set[str],
    indent: int,
) -> list[str]:
    block = program.block_for_state(state)
    if block is None:
        return []
    instructions = block.instructions
    if instructions and isinstance(instructions[-1], (Jump, Branch, Return)):
        instructions = instructions[:-1]
    lines: list[str] = []
    for instruction in instructions:
        lines.extend(_instruction_lines(instruction, names, declared, indent))
    return lines


def _region_lines(
    program: SemanticProgram,
    region: Region,
    names: dict[str, str],
    declared: set[str],
    indent: int,
) -> list[str]:
    if isinstance(region, SequenceRegion):
        lines: list[str] = []
        for item in region.items:
            lines.extend(_region_lines(program, item, names, declared, indent))
        return lines
    if isinstance(region, BlockRegion):
        return _block_effects(program, region.state, names, declared, indent)
    if isinstance(region, ReturnRegion):
        block = program.block_for_state(region.state)
        if block is None:
            return []
        lines = _block_effects(program, region.state, names, declared, indent)
        if block.instructions and isinstance(block.instructions[-1], Return):
            lines.extend(_instruction_lines(block.instructions[-1], names, declared, indent))
        return lines
    if isinstance(region, IfRegion):
        lines = _block_effects(program, region.state, names, declared, indent)
        prefix = "    " * indent
        lines.append(f"{prefix}if {_expr(region.condition, names)} then")
        lines.extend(_region_lines(program, region.true_region, names, declared, indent + 1))
        lines.append(f"{prefix}else")
        lines.extend(_region_lines(program, region.false_region, names, declared, indent + 1))
        lines.append(f"{prefix}end")
        return lines
    if isinstance(region, WhileRegion):
        lines = _block_effects(program, region.state, names, declared, indent)
        prefix = "    " * indent
        lines.append(f"{prefix}while {_expr(region.condition, names)} do")
        lines.extend(_region_lines(program, region.body, names, declared, indent + 1))
        lines.append(f"{prefix}end")
        return lines
    return []


def _emit_state_machine(program: SemanticProgram, names: dict[str, str]) -> str:
    lines = [f"local state = {program.entry_state if program.entry_state is not None else 'nil'}", "while state do"]
    declared = set(names.values())
    if declared:
        lines.insert(0, "local " + ", ".join(declared))
    for index, block in enumerate(program.blocks):
        keyword = "if" if index == 0 else "elseif"
        lines.append(f"    {keyword} state == {block.state} then")
        for instruction in block.instructions:
            if isinstance(instruction, Assign):
                target = _rename_expr(instruction.target, names)
                value = _expr(instruction.value, names)
                lines.append(f"        {emit_expr(target)} = {value}")
            else:
                lines.extend(_instruction_lines(instruction, names, declared, 2, include_control=True))
    lines.append("    else")
    lines.append('        error("unknown WAD VM state: " .. tostring(state))')
    lines.append("    end")
    lines.append("end")
    return "\n".join(lines) + "\n"


def emit_structured(program: SemanticProgram, region: Region) -> tuple[str, bool]:
    names = stable_names(program)
    if isinstance(region, StateMachineRegion):
        return _emit_state_machine(program, names), False
    declared: set[str] = set()
    lines = _region_lines(program, region, names, declared, 0)
    return ("\n".join(lines) + ("\n" if lines else "")), True
