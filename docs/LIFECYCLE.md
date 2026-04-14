# HybridComponent Lifecycle

Visual reference for how Python and JS communicate in a HybridComponent.
See [HYBRID_COMPONENTS_GUIDE.md](HYBRID_COMPONENTS_GUIDE.md) for the full tutorial.

## First Render

```mermaid
sequenceDiagram
    participant P as Python
    participant R as Rio Framework
    participant WS as WebSocket
    participant JS as JS Framework
    participant U as Your JS Class

    P->>R: Component created in build()
    R->>R: Serialize attributes + _custom_serialize_()
    R->>WS: updateComponentStates({id: 42, count: 5, ...})
    WS->>JS: delta_states received

    Note over JS: Phase 1 — Create new components
    JS->>U: createElement(context)
    U-->>JS: returns DOM element
    JS->>JS: Insert element into page

    Note over JS: Phase 2 — Update all components
    JS->>JS: super.updateElement() — layout props
    JS->>U: updateElement(deltaState, context)
    U->>U: Set text, styles, place children
```

## State Update

```mermaid
sequenceDiagram
    participant P as Python
    participant R as Rio Framework
    participant WS as WebSocket
    participant JS as JS Framework
    participant U as Your JS Class

    P->>P: self.count = 10
    P->>R: force_refresh()
    R->>R: Compute delta: {count: 10}
    R->>WS: updateComponentStates({id: 42, count: 10})
    WS->>JS: delta received

    Note over JS: Only changed props in deltaState
    JS->>JS: super.updateElement() — layout props
    JS->>U: updateElement({count: 10}, context)
    U->>U: Update only what changed
```

## JS → Python Message

```mermaid
sequenceDiagram
    participant U as Your JS Class
    participant JS as JS Framework
    participant WS as WebSocket
    participant P as Python

    U->>JS: this.__rioWrapper__.sendMessageToBackend({type: 'click'})
    JS->>WS: message sent
    WS->>P: _on_message_({type: 'click'})
    P->>P: Handle event, update state
    P->>P: force_refresh() → triggers State Update cycle
```
