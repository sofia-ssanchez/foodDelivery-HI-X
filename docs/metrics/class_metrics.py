#!/usr/bin/env python3
"""Measure selected Python classes at a Git ref without checking it out.

This is a supplementary, dependency-free measurement. It does not reproduce
SonarQube's proprietary/rule-specific complexity implementation. LOC is counted
as nonblank, non-comment physical lines inside the AST class span. Cyclomatic
complexity is reported as the sum of method McCabe scores, with each method
starting at 1 and decisions counted by DecisionCounter below.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import PurePosixPath


class DecisionCounter(ast.NodeVisitor):
    """Count McCabe decision points in one method, excluding nested scopes."""

    def __init__(self) -> None:
        self.count = 0

    def visit_If(self, node: ast.If) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.count += 1
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.count += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.count += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.count += 1  # each comprehension generator is a loop
        self.count += len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        # Every non-wildcard case adds an alternate path; the first case is
        # the baseline path. This construct is not used by current hotspots,
        # but defining it keeps the script repeatable if a target later uses it.
        non_wildcard = [
            case for case in node.cases
            if not isinstance(case.pattern, ast.MatchAs)
            or case.pattern.name is not None
        ]
        self.count += max(0, len(non_wildcard) - 1)
        for case in node.cases:
            for statement in case.body:
                self.visit(statement)
            if case.guard:
                self.visit(case.guard)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # A nested function is a separate function, not a decision path in
        # the containing method's score.
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def git_text(ref: str, path: str) -> str:
    return subprocess.check_output(
        ["git", "show", f"{ref}:{path}"], text=True, stderr=subprocess.PIPE
    )


def class_nodes(body: list[ast.stmt], prefix: str = ""):
    for statement in body:
        if isinstance(statement, ast.ClassDef):
            qualified = f"{prefix}.{statement.name}" if prefix else statement.name
            yield qualified, statement
            yield from class_nodes(statement.body, qualified)


def measure_class_node(
    source: str, path: str, qualified_name: str, node: ast.ClassDef
) -> dict[str, object]:
    lines = source.splitlines()
    class_lines = lines[node.lineno - 1 : node.end_lineno]
    loc = sum(
        bool(line.strip()) and not line.lstrip().startswith("#")
        for line in class_lines
    )
    methods = [
        member for member in node.body
        if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    method_scores: dict[str, int] = {}
    for method in methods:
        counter = DecisionCounter()
        for statement in method.body:
            counter.visit(statement)
        method_scores[method.name] = 1 + counter.count

    return {
        "class": qualified_name,
        "path": str(PurePosixPath(path)),
        "line_start": node.lineno,
        "line_end": node.end_lineno,
        "loc_nonblank_noncomment": loc,
        "cyclomatic_method_sum": sum(method_scores.values()),
        "method_cyclomatic": method_scores,
    }


def measure_class(source: str, path: str, class_name: str) -> dict[str, object]:
    tree = ast.parse(source, filename=path)
    matches = [
        (qualified, node)
        for qualified, node in class_nodes(tree.body)
        if qualified == class_name
    ]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one top-level class {class_name!r} in {path}, found {len(matches)}"
        )

    qualified, node = matches[0]
    return measure_class_node(source, path, qualified, node)


def all_source_classes(ref: str) -> list[dict[str, object]]:
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", ref], text=True
    ).splitlines()
    python_paths = [
        path for path in paths
        if path.endswith(".py")
        and (path.startswith("backend/") or path.startswith("frontend/src/"))
        and not any(
            part in {"migrations", "__pycache__", "node_modules", ".next", ".venv", "venv"}
            for part in PurePosixPath(path).parts
        )
    ]
    measured = []
    for path in python_paths:
        source = git_text(ref, path)
        tree = ast.parse(source, filename=path)
        measured.extend(
            measure_class_node(source, path, qualified, node)
            for qualified, node in class_nodes(tree.body)
        )
    return measured


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", required=True, help="Git tag, commit, or ref")
    parser.add_argument(
        "--class", dest="classes", action="append",
        metavar="PATH:CLASS", help="Python class (nested names use dots); repeatable",
    )
    parser.add_argument(
        "--all-source", action="store_true",
        help="Measure all Python classes under backend/ and frontend/src/ at the ref",
    )
    parser.add_argument("--output", help="Write JSON here; default is stdout")
    args = parser.parse_args()

    commit = subprocess.check_output(
        ["git", "rev-parse", f"{args.ref}^{{commit}}"], text=True
    ).strip()
    if not args.all_source and not args.classes:
        parser.error("provide at least one --class or use --all-source")
    results = all_source_classes(args.ref) if args.all_source else []
    for spec in args.classes or []:
        path, separator, name = spec.rpartition(":")
        if not separator or not path or not name:
            parser.error(f"Invalid --class {spec!r}; expected PATH:CLASS")
        results.append(measure_class(git_text(args.ref, path), path, name))

    report = {
        "measurement": "supplemental Python AST; not SonarQube metrics",
        "ref": args.ref,
        "commit": commit,
        "loc_method": "nonblank, non-comment physical lines in AST class span",
        "cyclomatic_method": (
            "sum of direct method McCabe scores; each method starts at 1; "
            "decision points: if/for/async-for/while/conditional-expression, "
            "except handler, each boolean operator after the first, each "
            "comprehension generator/filter, and match alternatives"
        ),
        "cognitive_complexity": "not measured by this script",
        "scope": (
            "all tracked Python source files under backend/ and frontend/src/, "
            "excluding migrations and __pycache__"
            if args.all_source else "only the explicitly selected classes"
        ),
        "classes": results,
    }
    serialized = json.dumps(report, indent=2) + "\n"
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            output.write(serialized)
    else:
        sys.stdout.write(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
