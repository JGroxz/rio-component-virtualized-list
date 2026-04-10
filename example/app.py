"""Interactive demo: 100k-item virtualized list in Rio."""

from __future__ import annotations

from textwrap import dedent

import rio

from rio_virtualized_list import VirtualizedList

_DEFAULT_TOTAL = 100_000
_DEFAULT_ROW_HEIGHT = 3.0
_DEFAULT_GAP = 0.3


class DemoPage(rio.Component):
    """Demo page with live controls for VirtualizedList."""

    # Configurable props
    _total_items: int = _DEFAULT_TOTAL
    _row_height: float = _DEFAULT_ROW_HEIGHT
    _gap: float = _DEFAULT_GAP
    _show_scrollbar: bool = True
    _snap: bool = False
    _auto_follow: bool = False
    _fade_duration: int = 110
    _stagger: int = 18

    def build(self) -> rio.Component:
        """Build the demo layout."""
        virtualized_list = VirtualizedList(
            item_count=self._total_items,
            row_height=self._row_height,
            gap=self._gap,
            snap=self._snap,
            build_row=self._build_row,
            auto_follow=self._auto_follow,
            show_scrollbar=self._show_scrollbar,
            fade_duration_ms=self._fade_duration,
            stagger_ms=self._stagger,
            key="demo-list",
            grow_x=True,
            grow_y=True,
        )

        # Store ref to the reconciled instance (first build creates it,
        # subsequent builds reconcile onto it — ref stays valid)
        if not hasattr(self, "_list"):
            object.__setattr__(self, "_list", virtualized_list)

        description = dedent(
            f"""
            A list of {self._total_items:,} complex Rio components.
            Only ~80 rows are rendered at a time as full Rio components — each with an icon, two text lines, a progress bar, and tag chips.
            Rows are built on the fly from the item index; no data is pre-generated. Scroll to see the render window shift.
            """
        )

        return rio.Column(
            rio.Text("VirtualizedList Demo", style="heading2"),
            rio.Text(
                description,
                selectable=False,
                overflow="wrap",
            ),
            self._build_controls(),
            rio.Row(
                rio.Button(
                    "Jump to top",
                    icon="remix/arrow-up-s",
                    on_press=self._jump_to_top,
                ),
                rio.Button(
                    "Jump to bottom",
                    icon="remix/arrow-down-s",
                    on_press=self._jump_to_bottom,
                ),
                rio.Button(
                    "Add 10 items",
                    icon="remix/add",
                    on_press=self._add_items,
                ),
                spacing=1,
                align_x=0.5,
                align_y=0.5,
            ),
            rio.Rectangle(
                content=virtualized_list,
                fill=rio.Color.BLACK,
                grow_x=True,
                grow_y=True,
            ),
            spacing=1,
            margin=2,
            grow_x=True,
            grow_y=True,
        )

    def _build_controls(self) -> rio.Component:
        """Build the live control panel."""
        muted = rio.Color.from_hex("#888")
        label_style = rio.TextStyle(fill=muted, font_size=0.7)

        def _slider(
            label: str, value: float, fmt: str, tip: str,
            lo: float, hi: float, setter: object,
        ) -> rio.Component:
            return rio.Tooltip(
                rio.Column(
                    rio.Text(f"{label}: {fmt}", style=label_style),
                    rio.Slider(
                        value=value, minimum=lo, maximum=hi,
                        on_change=setter, min_width=12,
                    ),
                    spacing=0.1,
                    grow_x=True,
                ),
                tip=tip,
            )

        return rio.Card(
            content=rio.Column(
                rio.Text("Controls", style=rio.TextStyle(font_weight="bold")),
                rio.Row(
                    _slider(
                        "item_count", self._total_items,
                        f"{self._total_items:,}",
                        "Total number of items in the list. Only a small window is rendered at a time.",
                        100, 500_000,
                        lambda e: self._set("_total_items", int(e.value)),
                    ),
                    _slider(
                        "row_height", self._row_height,
                        f"{self._row_height:.1f}",
                        "Height of each row in rem. All rows must have the same height.\n"
                        "If actual row content is bigger, it will be clipped to this height.",
                        1.5, 8.0,
                        lambda e: self._set("_row_height", round(e.value, 1)),
                    ),
                    _slider(
                        "gap", self._gap,
                        f"{self._gap:.1f}",
                        "Vertical gap between rows in rem.",
                        0.0, 2.0,
                        lambda e: self._set("_gap", round(e.value, 1)),
                    ),
                    _slider(
                        "fade_duration_ms", self._fade_duration,
                        str(self._fade_duration),
                        "Duration of the fade-in animation when new rows enter the viewport. Set to 0 to disable.",
                        0, 500,
                        lambda e: self._set("_fade_duration", int(e.value)),
                    ),
                    _slider(
                        "stagger_ms", self._stagger,
                        str(self._stagger),
                        "Delay between successive row fade-ins for a cascade effect. Set to 0 for simultaneous.",
                        0, 100,
                        lambda e: self._set("_stagger", int(e.value)),
                    ),
                    spacing=1.5,
                    grow_x=True,
                ),
                rio.Row(
                    self._toggle(
                        "show_scrollbar", self._show_scrollbar,
                        "Show a thin scrollbar for scroll position feedback.",
                    ),
                    self._toggle(
                        "snap", self._snap,
                        "Snap scrolling to row boundaries.",
                    ),
                    self._toggle(
                        "auto_follow", self._auto_follow,
                        "Automatically scroll to the bottom when new items are added. Useful for streaming/log use cases.\n"
                        "Try adding items to the list while this option is enabled - it will jump to bottom automatically.",
                    ),
                    spacing=2,
                    align_x=0,
                    align_y=0.5,
                ),
                spacing=0.8,
                margin=1,
                grow_x=True,
            ),
            grow_x=True,
        )

    def _toggle(self, label: str, value: bool, tip: str = "") -> rio.Component:
        """Build a labeled toggle with optional tooltip."""
        row = rio.Row(
            rio.Text(
                label,
                style=rio.TextStyle(
                    fill=rio.Color.from_hex("#888"),
                    font_size=0.75,
                ),
                selectable=False,
            ),
            rio.Switch(
                is_on=value,
                on_change=lambda e, attr=f"_{label}": self._set(attr, e.is_on),
            ),
            spacing=0.5,
            align_x=0,
            align_y=0.5,
        )
        if tip:
            return rio.Tooltip(row, tip=tip)
        return row

    def _set(self, attr: str, value: object) -> None:
        """Generic setter — reset scroll on structural changes."""
        setattr(self, attr, value)
        if attr in ("_total_items", "_row_height", "_gap") and hasattr(self, "_list"):
            self._list.scroll_to_top()
            return
        self.force_refresh()

    def _build_row(self, index: int) -> rio.Component:
        """Build a rich list row with icon, multi-line text, tags, and progress."""
        is_even = index % 2 == 0
        progress = (index * 37 % 100) / 100

        statuses = ["completed", "running", "pending", "failed"]
        status = statuses[index % len(statuses)]
        status_colors = {
            "completed": "#2ecc71",
            "running": "#3498db",
            "pending": "#95a5a6",
            "failed": "#e74c3c",
        }
        status_icons = {
            "completed": "remix/checkbox-circle",
            "running": "remix/play-circle",
            "pending": "remix/time",
            "failed": "remix/close-circle",
        }
        tags = ["alpha", "beta", "gamma", "delta", "epsilon"]
        item_tags = [tags[index % 5], tags[(index * 3) % 5]]

        icon = rio.Icon(
            status_icons[status],
            fill=rio.Color.from_hex(status_colors[status]),
            min_width=1.4,
            min_height=1.4,
        )

        title = rio.Text(
            f"Task {index:04d} — {status.title()}",
            style=rio.TextStyle(font_weight="bold"),
            selectable=False,
        )
        subtitle = rio.Text(
            f"worker-{index % 8} · {item_tags[0]}, {item_tags[1]} · {progress * 100:.0f}% complete",
            style=rio.TextStyle(
                fill=rio.Color.from_hex("#888"),
                font_size=0.8,
            ),
            selectable=False,
        )
        text_block = rio.Column(title, subtitle, spacing=0.1, grow_x=True)

        bar_fill = rio.Color.from_hex(status_colors[status])
        progress_bar = rio.Row(
            rio.Rectangle(
                fill=bar_fill,
                min_width=progress * 6,
                min_height=0.25,
                corner_radius=0.12,
            ),
            rio.Rectangle(
                fill=rio.Color.from_hex("#333"),
                min_height=0.25,
                corner_radius=0.12,
                grow_x=True,
            ),
            spacing=0,
            min_width=6,
        )

        chip_row = rio.Row(
            *[
                rio.Rectangle(
                    content=rio.Text(
                        tag,
                        style=rio.TextStyle(
                            fill=rio.Color.from_hex("#ccc"),
                            font_size=0.65,
                        ),
                        selectable=False,
                        margin_x=0.4,
                        margin_y=0.1,
                    ),
                    fill=rio.Color.from_hex("#2a2a3e"),
                    corner_radius=0.2,
                )
                for tag in item_tags
            ],
            spacing=0.3,
            align_y=0.5,
        )

        return rio.Rectangle(
            content=rio.Row(
                icon,
                text_block,
                rio.Column(progress_bar, chip_row, spacing=0.3, align_y=0.5),
                spacing=1,
                margin_x=1,
                align_y=0.5,
                grow_x=True,
            ),
            fill=rio.Color.from_hex("#1a1a2e" if is_even else "#16213e"),
            corner_radius=0.3,
            grow_x=True,
        )

    def _add_items(self) -> None:
        """Add 10 items to the end of the list."""
        self._total_items += 10
        self.force_refresh()

    def _jump_to_top(self) -> None:
        """Scroll to the top."""
        if hasattr(self, "_list"):
            self._list.scroll_to_top()

    def _jump_to_bottom(self) -> None:
        """Scroll to the bottom."""
        if hasattr(self, "_list"):
            self._list.scroll_to_bottom()


_THEME = rio.Theme.from_colors(
    primary_color=rio.Color.from_hex("#e63946"),
    mode="dark",
)

app = rio.App(
    name="VirtualizedList Demo",
    build=DemoPage,
    theme=_THEME,
)
