# rio-virtualized-list

High-performance virtualized list component for [Rio](https://rio.dev). Renders only the visible rows, supporting hundreds of thousands of items without performance degradation.

![Demo](docs/demo.gif)

## Features

- **Virtual scrolling** — only visible rows are rendered as Rio components
- **Fixed row height** — efficient absolute positioning, no layout thrashing
- **Scroll events** — Python controls the visible window via `on_scroll` callback
- **Auto-follow** — sticky-bottom mode for streaming/log use cases
- **Fade-in animation** — configurable stagger animation for new items
- **Optional scrollbar** — thin accent scrollbar for scroll position feedback

## Installation

```bash
uv add rio-virtualized-list
```

Or with pip:

```bash
pip install rio-virtualized-list
```

## Quick Start

Just provide a `build_row` callback and the component handles the rest:

```python
import rio
from rio_virtualized_list import VirtualizedList

class MyPage(rio.Component):
    def build(self) -> rio.Component:
        return VirtualizedList(
            item_count=100_000,
            row_height=3.0,
            build_row=self._build_row,
            grow_x=True,
            grow_y=True,
        )

    def _build_row(self, index: int) -> rio.Component:
        return rio.Rectangle(
            content=rio.Text(f"Item {index}", margin=0.5),
            fill=rio.Color.from_hex("#1a1a2e" if index % 2 == 0 else "#16213e"),
            grow_x=True,
        )
```

### Dynamic item count

The component doesn't own the data — you do. To add or remove items, update `item_count` on your parent component and call `force_refresh()`:

```python
def _add_items(self) -> None:
    self._total_items += 10
    self.force_refresh()
```

When `auto_follow=True`, the list automatically scrolls to show new items at the bottom.

## How It Works

The component uses a two-layer architecture:

1. **Python side** (`VirtualizedList`) — you provide `build_row` and the component manages the visible window automatically: tracking scroll position, deciding which rows to render, and rebuilding when the user scrolls past the buffer.

2. **JS side** (`_VrlScroller`) — a HybridComponent that manages a scrollable viewport with absolutely-positioned children. A sentinel div sets the total scroll height. Scroll events are debounced and sent to Python.

### Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `item_count` | `int` | `0` | Total number of items |
| `row_height` | `float` | `3.5` | Height of each row in rem |
| `build_row` | `Callable[[int], Component]` | — | Callback that builds a row from an index |
| `gap` | `float` | `0.0` | Gap between rows in rem |
| `snap` | `bool` | `False` | Snap scrolling to row boundaries |
| `auto_follow` | `bool` | `False` | Scroll to bottom on updates |
| `show_scrollbar` | `bool` | `False` | Show thin scrollbar |
| `horizontal_scroll` | `bool` | `False` | Allow rows wider than viewport to scroll horizontally instead of stretching |
| `fade_duration_ms` | `int` | `110` | Fade-in animation duration (0 to disable) |
| `stagger_ms` | `int` | `18` | Delay between successive fade-ins |
| `scroll_to_top()` | method | — | Programmatically scroll to the top |
| `scroll_to_bottom()` | method | — | Programmatically scroll to the bottom |

## Running the Example

```bash
git clone https://github.com/JGroxz/rio-component-virtualized-list.git
cd rio-component-virtualized-list
uv sync
uv run rio run
```

The demo shows 100k items with complex multi-component rows and live controls for all props, so that you can play with them and learn how it works.

## Building Your Own Custom Components

This package includes `HybridComponent` — a base class for writing custom
Python+JS components for Rio. See **[docs/HYBRID_COMPONENTS_GUIDE.md](docs/HYBRID_COMPONENTS_GUIDE.md)** for a full
tutorial on how to build your own components with custom JavaScript behavior.

## License

MIT
