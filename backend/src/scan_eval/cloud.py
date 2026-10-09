"""Cloud vision reader: one photo in, a list of spine reads out, with token usage and cost."""

from __future__ import annotations

import base64
import io
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from booked.matching import SpineRead

from .pricing import ModelSpec, Usage, compute_cost

SYSTEM_PROMPT = """You read the spines of books in a photograph of a bookshelf.

List every book whose spine you can see, shelf by shelf, left to right (right to left for
rows that are clearly Hebrew). Rules:
- Copy title and author exactly as printed, in the original script. Hebrew stays Hebrew; do not translate or transliterate.
- If the author is not on the spine, leave it empty. Never invent an author.
- If a spine is too small, blurred or hidden to read, include it with legible=false and an empty title. Do not guess.
- language is the language of the printed title as an ISO 639-1 code (he, en, fr, es, it, de, ...), or empty if unsure.
- confidence is your own certainty, from 0 to 1, that the title and author are read correctly.
- Ignore objects that are not books."""

SPINE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "spines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shelf": {"type": "integer"},
                    "position": {"type": "integer"},
                    "title": {"type": "string"},
                    "author": {"type": "string"},
                    "language": {"type": "string"},
                    "confidence": {"type": "number"},
                    "legible": {"type": "boolean"},
                },
                "required": ["shelf", "position", "title", "author", "language", "confidence", "legible"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["spines"],
    "additionalProperties": False,
}

_MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}


@dataclass
class ScanResult:
    photo: str
    model: str
    reads: list[dict] = field(default_factory=list)  # legible reads as dicts (JSON friendly)
    unreadable: int = 0
    usage: dict = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_s: float = 0.0
    error: str = ""

    def spine_reads(self) -> list[SpineRead]:
        return [
            SpineRead(r["title"], r.get("author", ""), r.get("language", ""), float(r.get("confidence", 1.0)))
            for r in self.reads
        ]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str) -> "ScanResult":
        return cls(**json.loads(line))


def prepare_image_bytes(data: bytes, *, max_edge: int = 2000) -> tuple[bytes, str]:
    """Decode, fix orientation, downscale and re-encode as JPEG. Model cost grows with pixels."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_edge, max_edge))
            buf = io.BytesIO()
            img.convert("RGB").save(buf, format="JPEG", quality=85)
    except UnidentifiedImageError as exc:
        raise ValueError("not a supported image; send JPEG, PNG or WebP (convert HEIC to JPEG first)") from exc
    return buf.getvalue(), "image/jpeg"


def prepare_image(path: Path, *, max_edge: int = 2000) -> tuple[bytes, str]:
    """Return (bytes, media_type) for a photo on disk."""
    suffix = path.suffix.lower()
    if suffix not in _MEDIA_TYPES:
        raise ValueError(f"unsupported image type {suffix!r}; convert HEIC to JPEG first")
    return prepare_image_bytes(path.read_bytes(), max_edge=max_edge)


def extract_json(text: str) -> dict:
    """Parse JSON from a model reply even if it is wrapped in prose or a code fence."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ValueError("no JSON object in reply")
    return json.loads(text[start : end + 1])


class CloudSpineReader:
    def __init__(self, client: Any, spec: ModelSpec, *, max_edge: int = 2000, max_tokens: int = 8000) -> None:
        self.client = client
        self.spec = spec
        self.max_edge = max_edge
        self.max_tokens = max_tokens

    def _request(self, data: bytes, media_type: str, *, structured: bool) -> dict:
        instruction = "List the book spines in this photo."
        if not structured:
            instruction += ' Reply with JSON only, shaped as {"spines": [ ... ]}.'
        kwargs: dict[str, Any] = {
            "model": self.spec.id,
            "max_tokens": self.max_tokens,
            "system": SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": base64.standard_b64encode(data).decode("ascii"),
                            },
                        },
                        {"type": "text", "text": instruction},
                    ],
                }
            ],
        }
        output_config: dict[str, Any] = {}
        if structured:
            output_config["format"] = {"type": "json_schema", "schema": SPINE_SCHEMA}
        if self.spec.supports_effort:
            output_config["effort"] = "low"
        if output_config:
            kwargs["output_config"] = output_config
        if self.spec.thinking:
            kwargs["thinking"] = self.spec.thinking
        return kwargs

    def read_photo(self, path: Path) -> ScanResult:
        try:
            data, media_type = prepare_image(path, max_edge=self.max_edge)
        except Exception as exc:
            return ScanResult(photo=path.name, model=self.spec.id, error=f"{type(exc).__name__}: {exc}")
        return self._read_prepared(path.name, data, media_type)

    def read_bytes(self, name: str, raw: bytes) -> ScanResult:
        """Read a photo that arrived as bytes (for example an upload). Nothing is written to disk."""
        try:
            data, media_type = prepare_image_bytes(raw, max_edge=self.max_edge)
        except Exception as exc:
            return ScanResult(photo=name, model=self.spec.id, error=f"{type(exc).__name__}: {exc}")
        return self._read_prepared(name, data, media_type)

    def _read_prepared(self, name: str, data: bytes, media_type: str) -> ScanResult:
        result = ScanResult(photo=name, model=self.spec.id)
        started = time.monotonic()
        try:
            try:
                response = self.client.messages.create(**self._request(data, media_type, structured=True))
            except Exception as exc:  # a model that rejects structured output falls back to plain JSON
                if "output_config" not in str(exc) and "format" not in str(exc):
                    raise
                response = self.client.messages.create(**self._request(data, media_type, structured=False))
            result.latency_s = time.monotonic() - started
            usage = Usage(
                input_tokens=getattr(response.usage, "input_tokens", 0) or 0,
                output_tokens=getattr(response.usage, "output_tokens", 0) or 0,
                cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0) or 0,
                cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", 0) or 0,
            )
            result.usage = asdict(usage)
            result.cost_usd = compute_cost(self.spec, usage)
            if response.stop_reason in ("refusal", "max_tokens"):
                result.error = f"stopped: {response.stop_reason}"
                return result
            text = next((b.text for b in response.content if getattr(b, "type", "") == "text"), "")
            for spine in extract_json(text).get("spines", []):
                if spine.get("legible", True) and str(spine.get("title", "")).strip():
                    result.reads.append(spine)
                else:
                    result.unreadable += 1
        except Exception as exc:  # keep a failed photo in the results so cost and failures stay visible
            result.latency_s = time.monotonic() - started
            result.error = f"{type(exc).__name__}: {exc}"
        return result
