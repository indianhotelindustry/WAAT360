from abc import ABC, abstractmethod

from src.ai.models import ExtractedInvoiceData


class AIProvider(ABC):
    """
    Abstract AI Provider Interface.
    Decouples document extraction from specific LLM vendors (Gemini, Claude, local OCR).
    """

    @abstractmethod
    def extract_invoice(
        self,
        file_bytes: bytes,
        filename: str,
        mime_type: str,
    ) -> ExtractedInvoiceData:
        """
        Extract structured invoice accounting data from document bytes.
        Returns validated ExtractedInvoiceData conforming to Indian GST requirements.
        """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name of the AI provider implementation."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name of the model version utilized."""
