"""Vision extraction module - extract text from poster images and PDFs."""

import io
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from ..llm.router import LLMRouter
from ..config import config


class VisionExtractor:
    """
    Extracts opportunity information from poster images and PDFs.
    Feature flag: ENABLE_VISION (default OFF)
    """

    def __init__(self, llm: LLMRouter):
        self.llm = llm
        self._vision_model = config.VISION_MODEL or "meta-llama/llama-3.2-90b-vision-instruct"

    async def extract_from_image(
        self,
        image_data: bytes,
        db: AsyncSession,
    ) -> Optional[dict]:
        """
        Extract opportunity fields from an image (poster/flyer).
        Returns extracted fields dict or None.
        """
        try:
            import base64

            # Encode image for vision model
            image_b64 = base64.b64encode(image_data).decode()

            prompt = """Extract all opportunity information from this poster image.

Read ALL text carefully. Numbers must be exact - double-check stipend amounts and deadlines.
If text is unclear, set the field to null.

Return JSON with these fields:
{
  "title": "Opportunity Title",
  "organization_name": "Organization",
  "opportunity_type": "Internship|Job|Hackathon|Fellowship",
  "location": "City",
  "stipend_min": 10000,
  "stipend_max": 15000,
  "stipend_currency": "INR",
  "stipend_period": "month",
  "registration_deadline": "2026-03-15",
  "deadline_type": "fixed|rolling|unspecified",
  "education_levels": ["BTech"],
  "skills_required": ["Python"],
  "apply_url": "https://example.com",
  "field_evidence": {
    "title": "Text as it appears in the image"
  }
}"""

            # Use vision-capable model via OpenAI-compatible API
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ]

            response = await self.llm.chat(
                messages=messages,
                prompt_version="vision_extractor_v1",
                db=db,
                temperature=0.1,
            )

            import json
            data = json.loads(response.text)

            # Add metadata
            data["_source_type"] = "image"
            data["_vision_model"] = self._vision_model

            return data

        except Exception as e:
            return {"_error": str(e), "_source_type": "image"}

    async def extract_from_pdf(
        self,
        pdf_data: bytes,
        db: AsyncSession,
    ) -> Optional[dict]:
        """
        Extract opportunity fields from a PDF document.
        Returns extracted fields dict or None.
        """
        try:
            # Extract text from PDF using pymupdf
            import fitz  # PyMuPDF

            text = ""
            with fitz.open(stream=pdf_data, filetype="pdf") as doc:
                for page in doc:
                    text += page.get_text()

            if not text.strip():
                return None

            # Use standard text extraction prompt
            from ..nodes.fetch_extract import fetch_extract

            # Create mock candidate
            candidate = {
                "url": "pdf_upload",
                "title": "PDF Document",
                "primary_source": "pdf_upload",
            }

            # Extract using text-based pipeline
            # Reuse the LLM extraction logic
            prompt = f"""Extract all opportunity fields from this PDF text.

PDF text:
{text[:8000]}

For each field, provide the exact quote as evidence. Return JSON."""

            response = await self.llm.chat(
                messages=[{"role": "user", "content": prompt}],
                prompt_version="extractor_v1",
                db=db,
                temperature=0.1,
            )

            import json
            data = json.loads(response.text)
            data["_source_type"] = "pdf"
            return data

        except Exception as e:
            return {"_error": str(e), "_source_type": "pdf"}
