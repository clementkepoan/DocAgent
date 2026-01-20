"""
Documentation Planning Schemas
================================

Type definitions for the documentation planning agent.
Used by doc_planner, plan_reviewer, and plan_executor.
"""

from typing import TypedDict, List, Optional


class DocumentationSection(TypedDict):
    """Represents a single section in the documentation plan"""
    section_id: str                    # e.g., "quick-start"
    title: str                         # e.g., "Quick Start"
    purpose: str                       # What this section should explain
    required_context: List[str]        # Which folders/modules to include
    style: str                         # e.g., "tutorial", "reference", "architecture"
    max_tokens: int                    # Recommended length
    dependencies: List[str]            # Other sections this depends on


class DocumentationPlan(TypedDict):
    """Complete documentation generation plan"""
    project_type: str                  # e.g., "CLI tool", "library", "web service"
    target_audience: str               # e.g., "developers", "end-users"
    primary_use_case: str              # What the project does
    architecture_pattern: str          # e.g., "layered", "microservices", "monolith"
    sections: List[DocumentationSection]  # Ordered list of sections
    glossary: List[dict]               # Key terms to define
