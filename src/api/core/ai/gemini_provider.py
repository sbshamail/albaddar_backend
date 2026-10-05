import base64
import json
from typing import Optional

import httpx

from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.api.core.response import raiseExceptions
from src.api.core.ai.schemas import AI_PRODUCT_SUGGESTION_SCHEMA, AIProductSuggestion

GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

SYSTEM_INSTRUCTION = (
    "You are a product data assistant for an e-commerce admin panel. Given a "
    "prompt from the shop owner (and optionally a photo of the product), fill "
    "in the requested product listing fields using the details given."
)


async def generate_product_suggestion(
    prompt: str,
    image_bytes: Optional[bytes] = None,
    image_mime_type: Optional[str] = None,
) -> AIProductSuggestion:
    raiseExceptions((GEMINI_API_KEY, 500, "GEMINI_API_KEY is not configured"))

    parts = [{"text": prompt}]
    if image_bytes:
        parts.append(
            {
                "inline_data": {
                    "mime_type": image_mime_type or "image/jpeg",
                    "data": base64.b64encode(image_bytes).decode("utf-8"),
                }
            }
        )

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "response_schema": AI_PRODUCT_SUGGESTION_SCHEMA,
        },
    }

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            GEMINI_API_URL,
            params={"key": GEMINI_API_KEY},
            json=payload,
        )

    raiseExceptions(
        (
            response.status_code == 200,
            502,
            f"Gemini API error ({response.status_code}): {response.text}",
        )
    )

    data = response.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raiseExceptions((False, 502, f"Unexpected Gemini response format: {exc}"))

    return AIProductSuggestion.model_validate(parsed)
