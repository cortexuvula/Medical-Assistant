# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) documenting significant architectural decisions made in the Medical Assistant project.

## What is an ADR?

An ADR is a document that captures an important architectural decision made along with its context and consequences. ADRs help future contributors understand why certain choices were made.

## ADR Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [ADR-001](001-tkinter-ui-framework.md) | Tkinter as UI Framework | Accepted | 2024-01 |
| [ADR-002](002-custom-agents-vs-langchain.md) | Custom Agents vs LangChain | Accepted | 2024-06 |
| [ADR-003](003-neon-neo4j-rag-architecture.md) | Neon + Neo4j for RAG | Accepted | 2024-08 |
| [ADR-004](004-provider-pattern-stt-tts.md) | Provider Pattern for STT/TTS | Accepted | 2024-03 |
| [ADR-005](005-sqlite-local-database.md) | SQLite for Local Storage | Accepted | 2024-01 |

## ADR Template

When creating a new ADR, use [template.md](template.md) as a starting point.

## Status Definitions

- **Proposed**: Under discussion
- **Accepted**: Decision has been made and implemented
- **Deprecated**: No longer relevant, superseded by another decision
- **Superseded**: Replaced by a newer ADR
