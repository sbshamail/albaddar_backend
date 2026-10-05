from typing import List, Optional

from pydantic import BaseModel


class AIProductAttribute(BaseModel):
    name: str
    value: str


class AIProductSuggestion(BaseModel):
    """Text fields an AI provider can suggest for a new product listing.
    Matches Product/ProductForm's own field names 1:1 so the frontend can
    drop this straight into its create-product form state. Images are
    never part of this — the admin uploads those themselves; AI only ever
    fills in text (and may *look at* a reference photo the admin sends,
    purely to inform its text suggestions)."""

    name: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    discount_price: Optional[float] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    whats_in_box: Optional[str] = None
    tags: Optional[List[str]] = None
    attributes: Optional[List[AIProductAttribute]] = None


# Hand-written rather than derived from the Pydantic model above —
# structured-output schemas sent to an LLM provider need to stay inside
# whatever subset of JSON Schema that provider actually supports (no
# $ref/$defs, limited "anyOf" support, etc.), which model_json_schema()
# does not guarantee. This is the literal shape asked of the model.
AI_PRODUCT_SUGGESTION_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Product title"},
        "short_description": {
            "type": "string",
            "description": (
                "One or two sentence summary for listing cards, as simple HTML "
                "(e.g. wrapped in <p>, with <strong> for emphasis). No headings, "
                "no <html>/<body> wrapper — just inline formatting."
            ),
        },
        "description": {
            "type": "string",
            "description": (
                "Full product description as simple, readable HTML — a couple of "
                "<p> paragraphs, and a <ul><li> bullet list for key features/specs "
                "when there are several. Use <strong> for emphasis where useful. "
                "No headings, scripts, or <html>/<body> wrapper — just the content "
                "markup, safe to render directly in a rich-text field."
            ),
        },
        "price": {
            "type": "number",
            "description": "Regular price — only if the prompt states or clearly implies one",
        },
        "discount_price": {
            "type": "number",
            "description": "Discounted/sale price — only if the prompt states or clearly implies one",
        },
        "meta_title": {
            "type": "string",
            "description": "SEO title, under 60 characters",
        },
        "meta_description": {
            "type": "string",
            "description": "SEO meta description, under 160 characters",
        },
        "whats_in_box": {
            "type": "string",
            "description": "What's included in the package, if inferable",
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Search/filter tags for the product",
        },
        "attributes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["name", "value"],
            },
            "description": "Key/value attributes evident from the prompt or photo — e.g. brand, material, color",
        },
    },
    "required": ["name"],
}
