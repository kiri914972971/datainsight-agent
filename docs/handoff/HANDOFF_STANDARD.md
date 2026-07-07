# HANDOFF_STANDARD.md

# Handoff Documentation Standard v1.0

Version: 1.0

Status: Stable

---

# 1. Purpose

Handoff documents record the **current implemented behavior** of a module.

They are intended for AI coding agents (Codex, ChatGPT, Claude Code, etc.) and future developers to quickly understand the current implementation state without reading the entire project.

Handoff documents are implementation documents.

They are **not** Product Requirement Documents (PRD), Specifications (Spec), or Architecture documents.

---

# 2. Responsibilities

Each documentation type has a single responsibility.

## PRD

Answers:

* Why is this product built?
* Who are the target users?
* What problem does it solve?

---

## Spec

Answers:

* Why is this module designed this way?
* What are the product goals?
* What are the design principles?
* What is included in MVP?

---

## Architecture

Answers:

* How is the system organized?
* How do modules interact?
* What are the major services and data flows?

---

## Handoff

Answers:

* What is currently implemented?
* How does the module behave today?
* What does this module depend on?
* What behaviors must not be broken?
* What future improvements are planned?

---

# 3. One Handoff per Development Module

A handoff represents one independently developed module.

Recommended examples:

* data_quality.md
* business_analysis.md
* visualization.md
* report_export.md
* modeling/table_relationship.md
* modeling/data_merge.md

Do not create one handoff for every small UI tab unless that tab becomes an independent long-term module.

---

# 4. Required Structure

Every handoff must follow this order exactly.

```
# Module

# Related Documents

# Module Lifecycle

# Current Status

# External Dependencies

# Key Files

# Implemented Features

# Important Design Decisions

# Data Flow / State Flow

# Known Issues

# Future Improvements

# Do Not Break

# Last Updated
```

Do not invent additional top-level sections unless they become project-wide standards.

---

# 5. Module Lifecycle

Allowed values:

* Planning
* Developing
* Testing
* Stable
* Maintenance
* Deprecated

Definitions:

Planning
Module design exists but implementation has not started.

Developing
Core functionality is under active development.

Testing
Implementation is complete and bug fixing is in progress.

Stable
Feature-complete and expected to receive only small improvements.

Maintenance
Only bug fixes or small enhancements are expected.

Deprecated
No longer maintained.

---

# 6. Behavior First Principle

Handoff documents describe **behavior**, not implementation details.

Good examples:

* Duplicate removal keeps the first row in each duplicate group.
* Preview never modifies the source dataset.
* Cleaned datasets are generated as separate project datasets.

Avoid implementation-specific descriptions such as:

* Calls `drop_duplicates(keep="first")`
* Uses function X internally
* Invokes helper Y

Implementation details belong to source code.

Behavior belongs to handoff.

---

# 7. Related Documents

Only reference documentation.

Examples:

* Specs
* Architecture
* Product Rules
* Acceptance Criteria

Do not list source code files here.

---

# 8. Key Files

Describe only the responsibility of each important file.

Good:

```
data_quality_service.py

Core data quality business logic.
```

Avoid listing internal helper functions or describing detailed implementations.

---

# 9. Current Status

Keep concise.

Recommended length:

3–6 lines.

Summarize:

* lifecycle
* implementation maturity
* major capabilities

Do not repeat the full feature list.

---

# 10. Implemented Features

Describe stable user-facing capabilities.

Prefer organizing by functional capability rather than by source code or UI widgets.

Example:

* Missing value analysis
* Duplicate handling
* Outlier detection
* Cleaned dataset generation

---

# 11. Known Issues

Record only confirmed limitations or implementation differences.

Examples:

* Current implementation differs from the original specification.
* Manual ID override is not persisted across browser sessions.

Do not use:

* TODO
* Verify later
* Maybe
* Needs verification

---

# 12. Future Improvements

Only record realistic future enhancements.

Do not include:

* Write tests
* Verify UI
* Refactor later

These belong to development tasks rather than module documentation.

---

# 13. Do Not Break

Record behaviors that future developers or AI agents must preserve.

Examples:

* Preview must never modify source datasets.
* Generated datasets must remain reusable.
* Duplicate removal must keep the first occurrence.
* Cleaning must not overwrite uploaded datasets.

This section protects project behavior during future refactoring.

---

# 14. Reality over Specification

When implementation differs from the specification:

Spec records the intended product design.

Handoff records the current implementation.

Never modify handoff to match outdated specifications.

If necessary, explicitly document the difference in "Known Issues".

---

# 15. When to Update a Handoff

Update the corresponding handoff when:

* module behavior changes
* user workflow changes
* public interfaces change
* data flow changes
* design decisions change
* dependencies change

Do not update handoff for:

* variable renaming
* formatting changes
* comments
* internal refactoring without behavior changes

---

# 16. Documentation Synchronization Rules

When coding:

* Behavior changes → update Handoff
* Product design changes → update Spec
* System architecture changes → update Architecture

Only update documentation related to the current task.

Do not modify unrelated documents.

---

End of Standard.
