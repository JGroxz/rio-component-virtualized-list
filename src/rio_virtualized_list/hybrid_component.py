"""HybridComponent — base class for Python+JS custom Rio components.

Extends ``FundamentalComponent`` with two features:

1. **Convention-based loading**: JS and CSS are loaded from sidecar files
   next to the Python module. A component in ``glow_container.py``
   automatically loads ``glow_container.js`` and ``glow_container.css``
   if they exist. No need to override ``build_javascript_source`` or
   ``build_css_source``.

2. **Full child support**: The JS wrapper passes ``context`` to the
   user's ``updateElement(deltaState, context)``, enabling calls to
   ``this.__rioWrapper__.replaceOnlyChild(context, ...)`` and
   ``this.__rioWrapper__.replaceChildren(context, ...)``.
   This is the same API that Rio's built-in components use.

File convention::

    my_component.py      # Python: subclasses HybridComponent
    my_component.js      # JS class: createElement + updateElement
    my_component.css     # CSS: component styles

JS file contract::

    // Class name MUST match the Python class name.
    //
    // deltaState keys:
    //   content   - ComponentId | null  (child component)
    //   glowColor - string              (CSS color)
    //
    class GlowContainer {
        createElement(context) {
            let el = document.createElement('div');
            return el;
        }

        updateElement(deltaState, context) {
            this.__rioWrapper__.replaceOnlyChild(context, deltaState.content);
        }

        deconstruct() {
            // Optional cleanup
        }
    }

Available via ``this.__rioWrapper__``::

    .id                                        — component ID (number)
    .state                                     — current full state object
    .element                                   — the DOM element
    .sendMessageToBackend(payload)             — send message to Python
    .replaceOnlyChild(context, childId)        — place a single child
    .replaceOnlyChild(context, childId, el)    — place in a specific parent el
    .replaceChildren(context, ids, el, wrap)   — place multiple children
"""

from __future__ import annotations

import json
from pathlib import Path

import rio
from rio import inspection
from rio.components.fundamental_component import (
    CSS_SOURCE_TEMPLATE,
    FundamentalComponent,
)
from uniserde import Jsonable

__all__ = ["HybridComponent"]


# Wrapper template that:
# - Calls super.updateElement() for layout property handling
# - Passes context to the user's updateElement and createElement
_WRAPPER_TEMPLATE = """\
(function () {

    %(js_source)s

    if (typeof %(js_user_class_name)s === 'undefined') {
        let message = `Failed to register component \\`%(cls_unique_id)s\\`: `
            + `class \\`%(js_user_class_name)s\\` not defined`;
        console.error(message);
        throw new Error(message);
    }

    class %(js_wrapper_class_name)s extends window.RIO_COMPONENT_BASE {
        createElement(context) {
            this.userInstance = new %(js_user_class_name)s();
            this.userInstance.__rioWrapper__ = this;
            let element = this.userInstance.createElement(context);
            this.userInstance.element = element;
            return element;
        }

        updateElement(deltaState, context) {
            super.updateElement(deltaState, context);
            this.userInstance.updateElement(deltaState, context);
        }
    }

    %(js_user_class_name)s.prototype.state = function () {
        return this.__rioWrapper__.state;
    }

    window.COMPONENT_CLASSES['%(cls_unique_id)s'] = %(js_wrapper_class_name)s;
    window.CHILD_ATTRIBUTE_NAMES['%(cls_unique_id)s'] = %(child_attribute_names)s;
})();
"""


def _sibling_path(cls: type, extension: str) -> Path | None:
    """Resolve a sidecar file next to the class's module.

    Args:
        cls: The component class.
        extension: File extension including dot (e.g. ``".js"``).

    Returns:
        Path to the sidecar file, or None if it doesn't exist.
    """
    import sys

    module = sys.modules.get(cls.__module__)
    if module is None or not hasattr(module, "__file__") or module.__file__ is None:
        return None

    path = Path(module.__file__).with_suffix(extension)
    return path if path.is_file() else None


class HybridComponent(FundamentalComponent):
    """Base class for Python+JS hybrid components.

    Subclass this for any component that needs custom JavaScript.
    Place a ``.js`` file (and optionally a ``.css`` file) next to the
    Python module — they'll be loaded automatically.

    The JS class name must match the Python class name exactly.

    Override ``build_javascript_source`` or ``build_css_source`` only
    if you need dynamic content (e.g. template substitution). Otherwise
    the sidecar files are used.
    """

    @classmethod
    def build_javascript_source(cls, sess: rio.Session) -> str:
        """Load JS from the sidecar ``.js`` file.

        Args:
            sess: The active Rio session.

        Returns:
            JavaScript source string, or empty string if no file found.
        """
        path = _sibling_path(cls, ".js")
        if path is None:
            return ""
        return path.read_text(encoding="utf-8")

    @classmethod
    def build_css_source(cls, sess: rio.Session) -> str:
        """Load CSS from the sidecar ``.css`` file.

        Args:
            sess: The active Rio session.

        Returns:
            CSS source string, or empty string if no file found.
        """
        path = _sibling_path(cls, ".css")
        if path is None:
            return ""
        return path.read_text(encoding="utf-8")

    @classmethod
    async def _initialize_on_client(cls, sess: rio.Session) -> None:
        """Register the component with a custom wrapper that passes context."""
        message_source = ""

        javascript_source = cls.build_javascript_source(sess)
        if javascript_source:
            message_source += _WRAPPER_TEMPLATE % {
                "js_source": javascript_source,
                "js_user_class_name": cls.__name__,
                "js_wrapper_class_name": f"{cls.__name__}Wrapper",
                "cls_unique_id": cls._unique_id_,
                "child_attribute_names": json.dumps(
                    inspection.get_child_component_containing_attribute_names(
                        cls
                    )
                ),
            }

        css_source = cls.build_css_source(sess)
        if css_source:
            escaped_css_source = json.dumps(css_source)
            message_source += CSS_SOURCE_TEMPLATE % {
                "escaped_css_source": escaped_css_source,
            }

        if message_source:
            await sess._evaluate_javascript(message_source)

    def _apply_state(self, delta: dict) -> None:
        """Apply a state delta with proper binding propagation.

        Use this instead of ``self.attr = value`` when the change
        originates from the frontend (e.g. inside ``_on_message_``).
        This triggers Rio's ``ObservableProperty`` descriptors and the
        ``AttributeBinding`` chain so that ``self.bind()`` two-way
        bindings propagate correctly to parent components.

        Args:
            delta: Mapping of attribute names to new values.
        """
        self._apply_delta_state_from_frontend(delta)

    async def _on_message_(self, message: Jsonable, /) -> None:
        """Override to handle messages from frontend JS.

        Args:
            message: Payload sent from JS via ``sendMessageToBackend``.
        """
        raise AssertionError(
            f"Frontend sent an unexpected message to `{type(self).__name__}`"
        )
