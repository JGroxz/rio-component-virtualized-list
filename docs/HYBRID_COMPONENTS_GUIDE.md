# Writing Custom Python+JS Components for Rio

This guide explains how the `VirtualizedList` component is built using
`HybridComponent` — a base class that bridges Python and JavaScript in Rio.
You can use this pattern to build any custom component with client-side
behavior.

## The Problem

Rio's built-in components cover common UI needs, but sometimes you need:
- Custom DOM events (scroll position, intersection, resize)
- CSS animations that survive Rio rebuilds
- Third-party JS libraries (maps, charts, editors)
- Custom rendering (canvas, SVG, WebGL)

Rio provides `FundamentalComponent` for this, but its JS wrapper doesn't
pass `context` to user code — so you can't place child components in the DOM.
`HybridComponent` fixes this.

## Architecture

### Component Structure

```
Python side                          JS side (browser)
─────────────                        ──────────────────
MyComponent(HybridComponent)    ←→   class MyComponent { ... }
  ├─ attributes (state)               ├─ createElement(context)
  ├─ _custom_serialize_()             ├─ updateElement(deltaState, context)
  └─ _on_message_(message)            └─ deconstruct()
                                           ↑
                                      this.__rioWrapper__
                                        ├─ .sendMessageToBackend()
                                        ├─ .replaceOnlyChild(context, id)
                                        └─ .replaceChildren(context, ids)
```

### Lifecycle Diagrams

See **[LIFECYCLE.md](LIFECYCLE.md)** for Mermaid sequence diagrams showing
the full render, update, and messaging cycles.

### Data Flow Summary

- **Python → JS (state):** Attribute changes on the Python object are
  serialized and sent to `updateElement(deltaState, context)` as a delta.
- **Python → JS (custom):** Override `_custom_serialize_()` to add computed
  values that aren't direct attributes.
- **JS → Python (messages):** Call `this.__rioWrapper__.sendMessageToBackend(payload)`.
  The payload arrives at `_on_message_(message)` on the Python side.

## File Convention

Place three sidecar files next to each other:

```
my_component.py    # Python class
my_component.js    # JS class (name MUST match Python class name)
my_component.css   # CSS styles (optional)
```

`HybridComponent` loads them automatically by filename convention.

```
ℹ️ This is different from how Rio itself manages client-side code for their components in the source repo. Since Rio's original components use TypeScript and need to be compiled, they are kept in a separate directory hierarchy.
In our implementation, we use JavaScript sidecar file convention for the sake of simplicity. 
```

## Step-by-Step: Building a Custom Component

### 1. Python file

```python
# counter.py
from __future__ import annotations
import rio
from uniserde import Jsonable, JsonDoc
from .hybrid_component import HybridComponent

class Counter(HybridComponent):
    """A button that counts clicks."""

    count: int = 0
    label: str = "Click me"

    def _custom_serialize_(self) -> JsonDoc:
        # Add any computed state for JS (beyond auto-serialized attrs)
        return {"displayText": f"{self.label}: {self.count}"}

    async def _on_message_(self, message: Jsonable, /) -> None:
        # Handle messages from JS
        if isinstance(message, dict) and message.get("type") == "click":
            self.count += 1
            self.force_refresh()
```

**Key points:**
- Public attributes (`count`, `label`) are auto-serialized as camelCase
  (`count`, `label`) in `deltaState`
- Private attributes (`_foo`) are NOT serialized
- `_custom_serialize_()` adds extra computed values
- `force_refresh()` triggers a new delta to be sent to JS

### 2. JS file

```javascript
// counter.js
//
// deltaState keys:
//   count       - number
//   label       - string
//   displayText - string (from _custom_serialize_)
//
class Counter {
    createElement(context) {
        let el = document.createElement('button');
        el.classList.add('my-counter');
        el.addEventListener('click', () => {
            this.__rioWrapper__.sendMessageToBackend({type: 'click'});
        });
        return el;
    }

    updateElement(deltaState, context) {
        if (deltaState.displayText !== undefined) {
            this.element.textContent = deltaState.displayText;
        }
    }

    deconstruct() {
        // Optional: cleanup listeners, timers, etc.
    }
}
```

**Key points:**
- Class name must match Python class name exactly (`Counter`)
- `createElement` runs once — create the DOM element
- `updateElement` runs on every state change — only changed props are in `deltaState`
- `this.element` is the DOM element returned by `createElement`
- `this.__rioWrapper__` gives access to Rio's component API

### 3. CSS file

```css
/* counter.css */
.my-counter {
    pointer-events: auto;  /* REQUIRED — Rio sets none on parent */
    padding: 0.5rem 1rem;
    cursor: pointer;
}
```

**Critical:** Always set `pointer-events: auto` — Rio's layout containers
set `pointer-events: none`. Without it, your element is invisible to clicks.

## Placing Child Components

If your component wraps Rio children, declare them as attributes:

```python
class MyPanel(HybridComponent):
    content: rio.Component | None = None
```

In JS, use `replaceOnlyChild` to place the child in the DOM:

```javascript
class MyPanel {
    createElement(context) {
        let el = document.createElement('div');
        el.classList.add('my-panel');
        return el;
    }

    updateElement(deltaState, context) {
        // Place child component — no-op if undefined
        this.__rioWrapper__.replaceOnlyChild(context, deltaState.content);
    }
}
```

For multiple children:

```python
class MyList(HybridComponent):
    children: list[rio.Component] = []
```

```javascript
updateElement(deltaState, context) {
    this.__rioWrapper__.replaceChildren(
        context, deltaState.children, this.element, true
    );
}
```

## State Serialization

| Python attribute | Serialized as | In deltaState |
|---|---|---|
| `count: int = 0` | `count` | `deltaState.count` |
| `row_height: float = 3.5` | `rowHeight` | `deltaState.rowHeight` |
| `_private: str = ""` | ❌ not serialized | — |
| `_custom_serialize_` return | merged into delta | any key you return |

**Important:** `deltaState` only contains **changed** properties. Always
check `if (deltaState.foo !== undefined)` before using a value.

Layout props (`_min_size_`, `_align_`, `_margin_`, `_grow_`) are handled
by `super.updateElement()` in the wrapper — your JS code never sees them.

## Communication Patterns

### JS → Python

```javascript
// In JS:
this.__rioWrapper__.sendMessageToBackend({
    type: 'scroll',
    start: 10,
    end: 50,
});
```

```python
# In Python:
async def _on_message_(self, message, /):
    if message.get("type") == "scroll":
        self._handle_scroll(message)
```

### Python → JS (via state)

```python
# Just change an attribute — Rio sends the delta automatically
self.count += 1
self.force_refresh()
```

### Python → JS (via _custom_serialize_)

```python
def _custom_serialize_(self):
    return {"computedValue": self._expensive_computation()}
```

**Note:** Values from `_custom_serialize_` are sent on every serialization,
not just when changed. Use attributes for values that change frequently.

## Extras

### Two-Layer Pattern

When your component needs to dynamically create child components (e.g.
from a callback), you need a two-layer design:

```
VirtualizedList (rio.Component)     ← has build(), creates children
    └─ _VirtualizedList (HybridComponent)  ← JS bridge, positions children
```

**Why:** Rio only allows component creation inside `build()` methods.
`FundamentalComponent` (and `HybridComponent`) don't have `build()`.

The outer `rio.Component` calls `build_row()` in its `build()` method
and passes the resulting components to the inner `HybridComponent`.

### Common Pitfalls

1. **Missing `pointer-events: auto`** — your component won't receive clicks
2. **JS class name mismatch** — must exactly match the Python class name
3. **Forgetting `deltaState` is partial** — only changed props are present
4. **Creating components outside `build()`** — Rio raises RuntimeError
5. **Mutating state in `build()`** — Rio raises RuntimeError
6. **`_custom_serialize_` creating components** — not allowed
7. **ESM imports in srcdoc iframes** — blocked by null origin

### How We Learned This

Rio's `FundamentalComponent` is documented in Rio's source code but not
extensively in the public docs. We learned by:

1. Reading Rio's built-in component source (Text, Button, Column, etc.)
2. Understanding the JS component lifecycle from the bundled frontend code
3. Tracing the serialization pipeline in `rio/session.py` and `rio/serialization.py`
4. Trial and error with the `_initialize_on_client` hook
5. Building progressively more complex components (detector → animated element → container → virtual scroller)

The `HybridComponent` base class encapsulates all the boilerplate so you
don't need to understand Rio's internals — just follow the file convention
and implement `createElement` / `updateElement`.
