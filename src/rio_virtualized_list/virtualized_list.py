"""Virtual scrolling list with Rio component items.

Usage::

    VirtualizedList(
        item_count=100_000,
        row_height=3.0,
        build_row=lambda index: rio.Text(f"Item {index}"),
    )
"""

from __future__ import annotations

from typing import Callable

import rio

from ._virtualized_list import _FADE_DURATION_MS, _STAGGER_MS, _VirtualizedList

__all__ = ["VirtualizedList"]

_BUFFER = 40


class VirtualizedList(rio.Component):
    """Virtual list that renders only the visible rows.

    Provide a ``build_row`` callback and the component handles
    scroll tracking and visible window management automatically.

    Programmatic scrolling uses ``scroll_to_top_seq`` and
    ``scroll_to_bottom_seq`` — increment them to trigger a scroll.

    Args:
        item_count: Total number of items.
        row_height: Height of each row in rem.
        build_row: Callback that receives an item index and returns
            a Rio component for that row.
        gap: Vertical gap between rows in rem.
        snap: Snap scrolling to row boundaries.
        auto_follow: Scroll to bottom on updates (streaming/log mode).
        show_scrollbar: Show a thin scrollbar.
        horizontal_scroll: Allow horizontal scrolling when rows are wider
            than the viewport. Off by default — rows stretch to viewport
            width. Turn on for log viewers, code views, wide tables where
            content shouldn't wrap.
        fade_duration_ms: Fade-in animation duration (0 to disable).
        stagger_ms: Delay between successive fade-ins.
    """

    item_count: int = 0
    row_height: float = 3.5
    build_row: Callable[[int], rio.Component] = lambda i: rio.Spacer()
    gap: float = 0.0
    snap: bool = False
    auto_follow: bool = False
    show_scrollbar: bool = False
    horizontal_scroll: bool = False
    fade_duration_ms: int = _FADE_DURATION_MS
    stagger_ms: int = _STAGGER_MS

    # Internal state
    _vl_start: int = 0
    _vl_end: int = _BUFFER * 2
    _scroll_top_seq: int = 0
    _scroll_bottom_seq: int = 0

    def scroll_to_top(self) -> None:
        """Scroll to the top of the list."""
        self._vl_start = 0
        self._vl_end = _BUFFER * 2
        self._scroll_top_seq += 1
        self.force_refresh()

    def scroll_to_bottom(self) -> None:
        """Scroll to the bottom of the list."""
        self._vl_start = max(0, self.item_count - _BUFFER * 2)
        self._vl_end = self.item_count
        self._scroll_bottom_seq += 1
        self.force_refresh()

    @rio.event.on_populate
    def _on_populate(self) -> None:
        """Keep window pinned to bottom when auto_follow is on."""
        if self.auto_follow and self.item_count > self._vl_end:
            self._vl_start = max(0, self.item_count - _BUFFER * 2)
            self._vl_end = self.item_count
            self._scroll_bottom_seq += 1

    def build(self) -> rio.Component:
        """Build the scroller with the current visible window."""
        start = max(0, self._vl_start)
        end = min(self._vl_end, self.item_count)
        items = [self.build_row(i) for i in range(start, end)]

        return _VirtualizedList(
            children=items,
            item_count=self.item_count,
            row_height=self.row_height,
            gap=self.gap,
            snap=self.snap,
            visible_start=start,
            auto_scroll_bottom=self.auto_follow,
            scroll_to_top_seq=self._scroll_top_seq,
            scroll_to_bottom_seq=self._scroll_bottom_seq,
            fade_duration_ms=self.fade_duration_ms,
            stagger_ms=self.stagger_ms,
            show_scrollbar=self.show_scrollbar,
            horizontal_scroll=self.horizontal_scroll,
            on_scroll=self._handle_scroll,
            grow_x=True,
            grow_y=True,
        )

    def _handle_scroll(self, msg: object) -> None:
        """Handle scroll — recenter buffer around visible range."""
        if not isinstance(msg, dict):
            return
        s = msg.get("start", 0)
        e = msg.get("end", _BUFFER * 2)

        if s >= self._vl_start and e <= self._vl_end:
            return

        mid = (s + e) // 2
        self._vl_start = max(0, mid - _BUFFER)
        self._vl_end = min(self.item_count, mid + _BUFFER)
        self.force_refresh()
