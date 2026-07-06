"""RandomGraphDialog — collect parameters for ``core.generate.random_graph``.

The dialog's ``values()`` returns EXACTLY the ``random_graph`` kwargs
(``node_count``, ``edge_density``, ``weight_range``, ``seed``, ``directed``,
``connected``) with the seed already resolved to a concrete int (F1). The same
concrete seed is exposed as ``resolved_seed`` (cached at accept()-time) so the
handler can echo a reproducible seed even when the user left the field blank.

The seed/validation/clamping logic lives in module-level functions so it can be
unit-tested without a QApplication.
"""
from __future__ import annotations

import random

from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

#: Upper bound for a resolved seed (fits a signed 32-bit int; QIntValidator too).
_SEED_MAX = 2 ** 31 - 1


def parse_seed(text) -> int | None:
    """Parse a seed field: digits-only -> int, empty/invalid -> None."""
    text = (text or "").strip()
    if not text or not text.isdigit():
        return None
    return int(text)


def resolve_seed(seed) -> int:
    """Return a concrete seed: pass an int through, draw a random one for None.

    A None seed draws from :class:`random.SystemRandom` so a blank field still
    yields a reproducible, echoable integer seed.
    """
    if seed is None:
        return random.SystemRandom().randrange(0, _SEED_MAX)
    return int(seed)


def normalize_weight_range(min_weight, max_weight) -> tuple[int, int]:
    """Return ``(min, max)`` with ``max`` clamped up to ``min`` when smaller."""
    min_weight = int(min_weight)
    max_weight = int(max_weight)
    if max_weight < min_weight:
        max_weight = min_weight
    return (min_weight, max_weight)


class RandomGraphDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Random Graph")
        self.resolved_seed: int | None = None

        self.node_spin = QSpinBox()
        self.node_spin.setRange(2, 50)
        self.node_spin.setValue(8)

        self.density_spin = QDoubleSpinBox()
        self.density_spin.setRange(0.0, 1.0)
        self.density_spin.setSingleStep(0.05)
        self.density_spin.setValue(0.25)

        self.weight_min_spin = QSpinBox()
        self.weight_min_spin.setRange(1, 99)
        self.weight_min_spin.setValue(1)

        self.weight_max_spin = QSpinBox()
        self.weight_max_spin.setRange(1, 99)
        self.weight_max_spin.setValue(9)
        # Keep max >= min as the user edits min.
        self.weight_min_spin.valueChanged.connect(self._sync_weight_max)

        self.seed_edit = QLineEdit()
        self.seed_edit.setPlaceholderText("random")
        self.seed_edit.setValidator(QIntValidator(0, _SEED_MAX, self))

        self.directed_check = QCheckBox()
        self.connected_check = QCheckBox()
        self.connected_check.setChecked(True)

        form = QFormLayout(self)
        form.addRow("Nodes", self.node_spin)
        form.addRow("Edge density", self.density_spin)

        weight_row = QWidget()
        weight_layout = QHBoxLayout(weight_row)
        weight_layout.setContentsMargins(0, 0, 0, 0)
        weight_layout.addWidget(self.weight_min_spin)
        weight_layout.addWidget(self.weight_max_spin)
        form.addRow("Weight min/max", weight_row)

        form.addRow("Seed", self.seed_edit)
        form.addRow("Directed", self.directed_check)
        form.addRow("Connected", self.connected_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _sync_weight_max(self, value: int) -> None:
        self.weight_max_spin.setMinimum(value)
        if self.weight_max_spin.value() < value:
            self.weight_max_spin.setValue(value)

    def accept(self) -> None:
        # Resolve the seed ONCE, at accept-time, so the generation is
        # reproducible and the concrete seed can be echoed in the status line.
        self.resolved_seed = resolve_seed(parse_seed(self.seed_edit.text()))
        super().accept()

    def values(self) -> dict:
        """Return the exact ``random_graph`` kwargs with a concrete int seed."""
        if self.resolved_seed is None:
            # Called before accept() (e.g. a headless test): resolve and cache
            # so values()["seed"] and resolved_seed always agree.
            self.resolved_seed = resolve_seed(parse_seed(self.seed_edit.text()))
        weight_range = normalize_weight_range(
            self.weight_min_spin.value(), self.weight_max_spin.value()
        )
        return {
            "node_count": self.node_spin.value(),
            "edge_density": self.density_spin.value(),
            "weight_range": weight_range,
            "seed": self.resolved_seed,
            "directed": self.directed_check.isChecked(),
            "connected": self.connected_check.isChecked(),
        }
