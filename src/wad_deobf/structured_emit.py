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
    MultiAssign,
    Name,
    Opaque,
    RawExpr,
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


def _has_raw_expr(expr: Expr) -> bool:
    if isinstance(expr, RawExpr):
        return True
    if isinstance(expr, Attribute):
        return _has_raw_expr(expr.base)
    if isinstance(expr, Index):
        return _has_raw_expr(expr.base) or _has_raw_expr(expr.key)
    if isinstance(expr, Concat):
        return any(_has_raw_expr(part) for part in expr.parts)
    if isinstance(expr, CallExpr):
        return _has_raw_expr(expr.callee) or any(_has_raw_expr(arg) for arg in expr.args)
    return False


def _can_rename(program: SemanticProgram) -> bool:
    for block in program.blocks:
        for instruction in block.instructions:
            if isinstance(instruction, Opaque):
                return False
            if isinstance(instruction, Assign):
                if _has_raw_expr(instruction.target) or _has_raw_expr(instruction.value):
                    return False
            elif isinstance(instruction, MultiAssign):
                if any(_has_raw_expr(target) for target in instruction.targets):
                    return False
                if any(_has_raw_expr(value) for value in instruction.values):
                    return False
            elif isinstance(instruction, Call):
                if _has_raw_expr(instruction.value):
                    return False
            elif isinstance(instruction, Branch):
                if _has_raw_expr(instruction.condition):
                    return False
            elif isinstance(instruction, Return):
                if any(_has_raw_expr(value) for value in instruction.values):
                    return False
    return True


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
    if isinstance(instruction, MultiAssign):
        targets = ", ".join(emit_expr(_rename_expr(target, names)) for target in instruction.targets)
        values = ", ".join(_expr(value, names) for value in instruction.values)
        return [f"{prefix}{targets} = {values}"]
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
        prefix = "    " * indent
        lines = [f"{prefix}while {_expr(region.condition, names)} do"]
        lines.extend(_region_lines(program, region.body, names, declared, indent + 1))
        lines.append(f"{prefix}end")
        return lines
    return []


def _emit_state_machine(program: SemanticProgram, names: dict[str, str]) -> str:
    declared_names = tuple(names.values())
    declared = set(declared_names)
    lines: list[str] = []
    if declared_names:
        lines.append("local " + ", ".join(declared_names))
    lines.extend([
        f"local state = {program.entry_state if program.entry_state is not None else 'nil'}",
        "while state do",
    ])
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
    stable = stable_names(program)
    names = stable if _can_rename(program) else {name: name for name in stable}
    if isinstance(region, StateMachineRegion):
        return _emit_state_machine(program, names), False

    declared_names = tuple(names.values())
    declared = set(declared_names)
    lines: list[str] = []
    if declared_names:
        lines.append("local " + ", ".join(declared_names))
    lines.extend(_region_lines(program, region, names, declared, 0))
    return ("\n".join(lines) + ("\n" if lines else "")), True
