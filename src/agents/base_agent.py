# -*- coding: utf-8 -*-
"""Abstract base class for specialist analysis agents."""

from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseAgent(ABC):
    """Abstract base class for specialist analysis agents.

    Each agent specializes in one dimension of stock analysis
    (technical, fundamental, or news/sentiment) and produces
    a focused report that the SynthesizerAgent combines into
    a final AnalysisResult.
    """

    def __init__(self, name: str, role: str):
        self.name = name
        self.role = role

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt defining this specialist's role and expertise."""

    @abstractmethod
    def build_prompt(self, code: str, context: Dict[str, Any]) -> str:
        """Build the full analysis prompt (instructions + data) for this specialist.

        Args:
            code: Stock code (e.g. '600519')
            context: Analysis context dict from storage.get_analysis_context()

        Returns:
            Complete prompt string to send to the LLM.
        """
