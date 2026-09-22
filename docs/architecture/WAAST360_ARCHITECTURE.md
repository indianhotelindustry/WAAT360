# WAAST360 Architecture

## Core Architectural Directives
- **No throwaway logic:** Lite must use the Prime-grade foundation.
- **Provider Abstraction:** Critical external dependencies must be abstracted.

## AI Provider Abstraction
```mermaid
classDiagram
    class AIProvider {
        <<interface>>
        +extract(document)
    }
    class GeminiProvider {
        +extract(document)
    }
    class ClaudeProvider {
        +extract(document)
    }
    class FutureProvider {
        +extract(document)
    }
    AIProvider <|-- GeminiProvider
    AIProvider <|-- ClaudeProvider
    AIProvider <|-- FutureProvider
```

## Tally Adapter Abstraction
```mermaid
classDiagram
    class TallyAdapter {
        <<interface>>
        +post(voucher)
        +query(filter)
    }
    class JSONAdapter {
        +post(voucher)
        +query(filter)
    }
    class XMLAdapter {
        +post(voucher)
        +query(filter)
    }
    TallyAdapter <|-- JSONAdapter
    TallyAdapter <|-- XMLAdapter
```

## Key Subsystems
1. **WAAST360 Core API:** Orchestrates proposals, approvals, and AI extraction.
2. **WAAST360 Web UI:** The user interface for interacting with proposals.
3. **WAAST360 Bridge:** A local agent that sits next to Tally and securely executes commands.
