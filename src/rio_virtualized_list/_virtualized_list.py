"""Low-level JS scroll viewport. Not part of the public API."""

from __future__ import annotations

import rio
from uniserde import Jsonable, JsonDoc

from .hybrid_component import HybridComponent

_SCROLL_DEBOUNCE_MS = 80
_FADE_DURATION_MS = 110
_STAGGER_MS = 18


class _VirtualizedList(HybridComponent):
    """Scroll viewport with absolute child positioning.

    Children are placed in a scrollable div and positioned absolutely
    by the JS side. A sentinel div sets total scroll height.
    """

    children: list[rio.Component] = []
    item_count: int = 0
    row_height: float = 3.5
    gap: float = 0.0
    snap: bool = False
    visible_start: int = 0
    auto_scroll_bottom: bool = False
    scroll_to_top_seq: int = 0
    scroll_to_bottom_seq: int = 0
    fade_duration_ms: int = _FADE_DURATION_MS
    stagger_ms: int = _STAGGER_MS
    show_scrollbar: bool = False
    horizontal_scroll: bool = False
    on_scroll: rio.EventHandler[Jsonable] = None  # type: ignore[assignment]
    on_auto_follow_change: rio.EventHandler[Jsonable] = None  # type: ignore[assignment]

    def _custom_serialize_(self) -> JsonDoc:
        """Serialize state for the frontend."""
        return {
            "rowHeight": self.row_height,
            "gap": self.gap,
            "snap": self.snap,
            "itemCount": self.item_count,
            "visibleStart": self.visible_start,
            "autoScrollBottom": self.auto_scroll_bottom,
            "scrollToTopSeq": self.scroll_to_top_seq,
            "scrollToBottomSeq": self.scroll_to_bottom_seq,
            "debounceMs": _SCROLL_DEBOUNCE_MS,
            "fadeDur": self.fade_duration_ms,
            "fadeStagger": self.stagger_ms,
            "showScrollbar": self.show_scrollbar,
            "horizontalScroll": self.horizontal_scroll,
        }

    async def _on_message_(self, message: Jsonable, /) -> None:
        """Route messages from JS to the appropriate handler."""
        if not isinstance(message, dict):
            return
        msg_type = message.get("type")
        if msg_type == "scroll":
            await self.call_event_handler(self.on_scroll, message)
        elif msg_type == "auto_follow":
            await self.call_event_handler(self.on_auto_follow_change, message)
