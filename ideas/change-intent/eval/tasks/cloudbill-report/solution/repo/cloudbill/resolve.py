"""Restatements, resolved without holding the export in memory.

A restated line item is the same ``line_item_id`` appearing again with a later ``last_updated``; the
version with the latest ``last_updated`` wins wherever the versions appear (later in the input wins a
tie). Finding them needs to know, for every row, whether its id appears anywhere else, and a set of every
id in a 2 GB export would not fit in the memory budget. So the input is read twice:

1. Pass one validates every file, collects the rejected rows, and writes a 64-bit hash of every line
   item id into fixed-size arrays that are sorted and spilled to temporary files. Merging the sorted
   runs finds the hashes that occur more than once. Memory: one run being sorted (about 10 MB) plus
   the repeated hashes.
2. Pass two yields every row whose hash occurred once, as it is read. Rows whose hash repeats (the
   restatements, plus the rare different ids that share a hash) are held, keyed by their exact id, and
   only the winning version of each is yielded at the end. Memory grows with the number of restated
   line items, never with the size of the export.

The hash is Python's own string hash, which is stable within one process; both passes run in the same
process, and a collision only costs an id the exact comparison in pass two.
"""

from __future__ import annotations

import heapq
import os
import tempfile
from array import array
from pathlib import Path
from typing import Iterable, Iterator

from .export import LineItem, Reject, read_export

MASK = (1 << 64) - 1
RUN = 1 << 18  # hashes per sorted run: 2 MB as an array, about 10 MB while it is sorted


def _hash(line_item_id: str) -> int:
    return hash(line_item_id) & MASK


def _read_run(path: str) -> Iterator[int]:
    with open(path, "rb") as fh:
        while True:
            block = array("Q")
            try:
                block.fromfile(fh, 8192)
            except EOFError:
                pass
            if not block:
                return
            yield from block


def _repeated(runs: list[str], last: array) -> set[int]:
    streams = [_read_run(p) for p in runs] + [iter(last)]
    repeated: set[int] = set()
    previous = None
    for h in heapq.merge(*streams):
        if h == previous:
            repeated.add(h)
        previous = h
    return repeated


class Input:
    """The rows of one or more export files, with restatements resolved. Construct it (pass one, which
    raises ExportError for an unusable file before anything is printed), then iterate ``items()``."""

    def __init__(self, paths: Iterable[str | Path]):
        self.paths = [Path(p) for p in paths]
        self.rejects: list[Reject] = []
        self.rows_read = 0
        runs: list[str] = []
        current = array("Q")
        tmp = tempfile.mkdtemp(prefix="cloudbill-")
        try:
            for index, path in enumerate(self.paths):
                for row in read_export(path, index):
                    if isinstance(row, Reject):
                        self.rejects.append(row)
                        continue
                    self.rows_read += 1
                    current.append(_hash(row.line_item_id))
                    if len(current) >= RUN:
                        current = array("Q", sorted(current))
                        name = os.path.join(tmp, f"run{len(runs)}")
                        with open(name, "wb") as fh:
                            current.tofile(fh)
                        runs.append(name)
                        current = array("Q")
            self._repeated = _repeated(runs, array("Q", sorted(current)))
        finally:
            for name in runs:
                os.unlink(name)
            os.rmdir(tmp)

    def items(self) -> Iterator[LineItem]:
        held: dict[str, LineItem] = {}
        repeated = self._repeated
        for index, path in enumerate(self.paths):
            for row in read_export(path, index):
                if isinstance(row, Reject):
                    continue
                if _hash(row.line_item_id) not in repeated:
                    yield row
                    continue
                current = held.get(row.line_item_id)
                if current is None or (row.last_updated, row.order) > (current.last_updated, current.order):
                    held[row.line_item_id] = row
        yield from sorted(held.values(), key=lambda item: item.order)
