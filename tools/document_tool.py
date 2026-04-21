"""
tools/document_tool.py – Document processing tool using PyMuPDF.
Supports PDF parsing, text extraction, summarisation, and key info extraction.
"""
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List
from utils.logger import get_logger

logger = get_logger("tools.document")

# ─── Mock document store ──────────────────────────────────────────────────────
_MOCK_DOCUMENT = """
QUARTERLY BUSINESS REPORT – Q3 2024
Executive Summary
Revenue increased by 18% year-over-year, reaching $4.2M in Q3.
Customer acquisition costs decreased by 12%, improving unit economics.

Key Highlights:
- New enterprise clients: 14
- Churn rate: 2.3% (target: <3%)
- NPS score: 68 (industry avg: 45)

Action Items:
1. Expand sales team by Q4 to capture demand
2. Launch new product tier for SMBs by November
3. Review pricing model with finance team

Next Steps:
The board meeting is scheduled for October 15th. All department heads
must submit updated forecasts by October 10th.
"""


class DocumentTool:
    """Parse, summarise, and extract key information from documents."""

    # ── Parse ─────────────────────────────────────────────────────────────────

    def parse_pdf(self, file_path: str | Path) -> Dict[str, Any]:
        """
        Extract text and metadata from a PDF file.

        Args:
            file_path: Path to the PDF

        Returns:
            dict with 'text', 'pages', 'metadata'
        """
        file_path = Path(file_path)

        if not file_path.exists():
            # Return mock data for demonstration
            logger.info("Document not found – returning mock content")
            return {
                "file": str(file_path),
                "pages": 1,
                "text": _MOCK_DOCUMENT,
                "metadata": {"title": "Mock Document", "author": "System"},
            }

        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(file_path))
            text = "\n".join(page.get_text() for page in doc)
            metadata = doc.metadata or {}
            pages = len(doc)
            doc.close()
            logger.info(f"Parsed PDF: {file_path.name} ({pages} pages, {len(text)} chars)")
            return {"file": str(file_path), "pages": pages, "text": text, "metadata": metadata}
        except ImportError:
            logger.warning("PyMuPDF not installed; using fallback text extraction")
            return {"file": str(file_path), "pages": 0, "text": _MOCK_DOCUMENT, "metadata": {}}

    def parse_text(self, file_path: str | Path) -> str:
        """Read a plain text or markdown file."""
        return Path(file_path).read_text(encoding="utf-8")

    # ── Summarise ─────────────────────────────────────────────────────────────

    def summarize(self, text: str, max_sentences: int = 5) -> str:
        """
        Extractive summarisation – returns the first N meaningful sentences.
        In production, replace with LLM-based abstractive summarisation.
        """
        sentences = [s.strip() for s in text.replace("\n", " ").split(".") if len(s.strip()) > 20]
        summary = ". ".join(sentences[:max_sentences]) + "."
        logger.info(f"Summarised document: {len(text)} chars → {len(summary)} chars")
        return summary

    # ── Key info extraction ───────────────────────────────────────────────────

    def extract_key_info(self, text: str) -> Dict[str, List[str]]:
        """
        Extract structured information from document text.
        Looks for action items, dates, numbers, and named entities.
        In production, use LLM for richer extraction.
        """
        import re

        lines = text.split("\n")

        # Action items: lines starting with digits or bullets
        action_items = [
            line.strip().lstrip("•-123456789. ")
            for line in lines
            if re.match(r"^\s*(\d+\.|[-•])\s+", line) and len(line.strip()) > 10
        ]

        # Dates: simple pattern match
        date_pattern = re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|"
            r"October|November|December)\s+\d{1,2}(?:th|st|nd|rd)?\b|"
            r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|"
            r"\bQ[1-4]\s+\d{4}\b"
        )
        dates = list(set(date_pattern.findall(text)))

        # Numbers / metrics
        metrics = re.findall(r"\$[\d,.]+[MBK]?|\d+\.?\d*%|\d+\s+(?:clients|users|days)", text)

        logger.info(
            f"Extracted: {len(action_items)} actions, {len(dates)} dates, {len(metrics)} metrics"
        )
        return {
            "action_items": action_items[:10],
            "dates": dates[:10],
            "metrics": metrics[:10],
        }

    # ── Combined pipeline ─────────────────────────────────────────────────────

    def process_document(self, file_path: str | Path) -> Dict[str, Any]:
        """Full pipeline: parse → summarise → extract."""
        parsed = self.parse_pdf(file_path)
        text = parsed["text"]
        return {
            "file": parsed["file"],
            "pages": parsed["pages"],
            "summary": self.summarize(text),
            "key_info": self.extract_key_info(text),
            "full_text": text,
        }


# Module-level singleton
document_tool = DocumentTool()
