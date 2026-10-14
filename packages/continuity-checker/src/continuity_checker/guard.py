"""Reports are written outside the inputs. The checkers never open a draft for writing."""

from __future__ import annotations

from pathlib import Path


class GuardError(Exception):
    """A report path would land inside an input file or folder."""


def reject_output_inside_inputs(inputs: list[Path], outputs: list[Path]) -> None:
    roots = [_input_root(path) for path in inputs]
    files = [path.expanduser().resolve() for path in inputs if path.expanduser().resolve().is_file()]
    for output in outputs:
        if str(output) == "-":
            continue
        dest = output.expanduser().resolve()
        for root in roots:
            if dest == root or root in dest.parents:
                raise GuardError(
                    f"refusing to write {output} inside the input tree {root}. "
                    "Reports go in a separate folder."
                )
        for source in files:
            if dest == source:
                raise GuardError(f"refusing to overwrite input {source} with a report.")


def _input_root(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.is_dir():
        return resolved
    return resolved.parent
