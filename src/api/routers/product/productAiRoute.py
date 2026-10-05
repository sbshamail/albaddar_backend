from typing import Optional

from fastapi import APIRouter, File, Form, UploadFile

from src.api.core.ai.gemini_provider import generate_product_suggestion
from src.api.core.dependencies import requireShopPermission
from src.api.core.response import api_response

router = APIRouter(prefix="/product/ai", tags=["Product AI"])

# Prompt tips for the frontend (state facts plainly, one per clause — the
# model fills every field it's explicitly given but won't invent numbers):
#   "Essential water bottle, price is 2000, discount price is 1500, color
#    black, material stainless steel, capacity 1 liter"
# Attaching a photo works the same way and lets the model describe what's
# actually in it (useful when the owner doesn't want to type details out):
#   "Get me the product create fields for this" + an image of the item


@router.post("/generate")
async def generate_product_fields(
    prompt: str = Form(...),
    image: Optional[UploadFile] = File(None),
    user=requireShopPermission(["product:create"]),
):
    """Turns an admin's free-text prompt (optionally with a reference photo)
    into suggested text fields for the product-create form. Text only — the
    admin still uploads their own product images through the normal create
    flow; this never touches media storage or creates a Product row."""
    image_bytes = None
    image_mime_type = None
    if image is not None:
        image_bytes = await image.read()
        image_mime_type = image.content_type

    suggestion = await generate_product_suggestion(
        prompt=prompt,
        image_bytes=image_bytes,
        image_mime_type=image_mime_type,
    )

    return api_response(200, "Product suggestion generated", suggestion)
