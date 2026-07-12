"""Guided repository inspection without taking model lifecycle ownership from Lemonade."""
from __future__ import annotations

from urllib.parse import quote, urlencode

import httpx
import psutil

from app.models.intake import FormatAssessment, IntakeReport, IntakeSearchResult, IntakeVariant


class HuggingFaceIntakeService:
    def __init__(self, provider, client: httpx.AsyncClient | None = None) -> None:
        self.provider = provider
        self.client = client

    async def inspect(self, repo_id: str) -> IntakeReport:
        memory = psutil.virtual_memory()
        ram_total_gb = round(memory.total / 1024**3, 2)
        ram_available_gb = round(memory.available / 1024**3, 2)
        variants_payload: dict | None = None
        variants_error: str | None = None
        try:
            variants_payload = await self.provider.get_pull_variants(repo_id)
        except Exception as exc:
            variants_error = str(exc)

        hub_payload: dict | None = None
        hub_error: str | None = None
        try:
            hub_payload = await self._hub_metadata(repo_id)
        except Exception as exc:
            hub_error = str(exc)

        if variants_payload is None and hub_payload is None:
            raise ValueError(f"Repository inspection failed. Lemonade: {variants_error}; Hugging Face: {hub_error}")

        suggested_name = (
            str((variants_payload or {}).get("suggested_name") or repo_id.split("/", 1)[1])
        )

        labels = [str(item) for item in (variants_payload or {}).get("suggested_labels", [])]
        mmproj_files = [str(item) for item in (variants_payload or {}).get("mmproj_files", [])]
        variants = self._gguf_variants(variants_payload or {}, ram_available_gb)
        siblings = self._siblings(hub_payload or {})
        onnx_files = [item for item in siblings if item["name"].lower().endswith(".onnx")]
        variants.extend(self._onnx_variants(onnx_files, ram_available_gb))

        has_gguf = bool(variants_payload and variants_payload.get("variants")) or any(
            item["name"].lower().endswith(".gguf") for item in siblings
        )
        formats = [
            FormatAssessment(
                format="gguf",
                applicability="applicable" if variants_payload and variants_payload.get("variants") else ("possible" if has_gguf else "unsupported"),
                recipe=str((variants_payload or {}).get("recipe") or "llamacpp") if has_gguf else None,
                evidence="Lemonade /pull/variants returned installable variants." if variants_payload and variants_payload.get("variants") else ("Hugging Face metadata contains GGUF files, but Lemonade exposed no ranked variant." if has_gguf else "No GGUF files were observed."),
            ),
            FormatAssessment(
                format="onnx",
                applicability="possible" if onnx_files else "unsupported",
                recipe="oga" if onnx_files else None,
                evidence=f"Hugging Face metadata contains {len(onnx_files)} ONNX file(s); recipe compatibility still requires Lemonade confirmation." if onnx_files else "No ONNX files were observed.",
            ),
        ]
        warnings = []
        raw_variant_count = len((variants_payload or {}).get("variants", []))
        if raw_variant_count > len([item for item in variants if item.format == "gguf"]):
            warnings.append(
                f"LCC shows the first 5 Lemonade-ranked GGUF variants out of {raw_variant_count}; use Lemonade directly for other quantizations."
            )
        if variants_error:
            warnings.append(f"Lemonade GGUF variant inspection was unavailable: {variants_error}")
        if hub_error:
            warnings.append(f"Hugging Face file metadata was unavailable: {hub_error}")
        if onnx_files:
            warnings.append("ONNX presence is not proof that the repository layout is directly loadable by Lemonade OGA.")
        recommended = next((item.name for item in variants if item.format == "gguf" and item.memory_risk == "low"), None)
        return IntakeReport(
            repo_id=repo_id,
            suggested_model_name=f"user.{suggested_name}",
            suggested_labels=labels,
            mmproj_files=mmproj_files,
            formats=formats,
            variants=variants,
            ram_total_gb=ram_total_gb,
            ram_available_gb=ram_available_gb,
            recommended_variant=recommended,
            warnings=warnings,
            inspection_sources=[source for source, value in (("Lemonade /pull/variants", variants_payload), ("Hugging Face repository metadata", hub_payload)) if value is not None],
        )

    async def search(self, query: str) -> list[IntakeSearchResult]:
        params = urlencode({
            "search": query,
            "filter": "gguf",
            "sort": "downloads",
            "direction": "-1",
            "limit": "5",
        })
        payload = await self._hub_get(f"https://huggingface.co/api/models?{params}")
        if not isinstance(payload, list):
            raise ValueError("Hugging Face search returned an unexpected response.")
        results = []
        for item in payload[:5]:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            results.append(IntakeSearchResult(
                repo_id=str(item["id"]),
                downloads=item.get("downloads") if isinstance(item.get("downloads"), int) else None,
                gated=item.get("gated") if isinstance(item.get("gated"), (bool, str)) else None,
                last_modified=str(item["lastModified"]) if item.get("lastModified") else None,
                tags=[str(tag) for tag in item.get("tags", [])[:8]],
            ))
        return results

    async def _hub_metadata(self, repo_id: str) -> dict:
        url = f"https://huggingface.co/api/models/{quote(repo_id, safe='/')}?blobs=true"
        payload = await self._hub_get(url)
        if not isinstance(payload, dict):
            raise ValueError("Hugging Face metadata returned an unexpected response.")
        return payload

    async def _hub_get(self, url: str):
        if self.client is not None:
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _siblings(payload: dict) -> list[dict]:
        result = []
        for item in payload.get("siblings", []):
            if not isinstance(item, dict) or not item.get("rfilename"):
                continue
            size = item.get("size")
            blob = item.get("lfs") if isinstance(item.get("lfs"), dict) else {}
            result.append({"name": str(item["rfilename"]), "size": size if isinstance(size, int) else blob.get("size")})
        return result

    @classmethod
    def _gguf_variants(cls, payload: dict, available_gb: float) -> list[IntakeVariant]:
        result = []
        for item in payload.get("variants", [])[:5]:
            if not isinstance(item, dict):
                continue
            size = item.get("size_bytes") if isinstance(item.get("size_bytes"), int) else None
            estimate, risk, fits = cls._memory_estimate(size, available_gb, 1.15)
            result.append(IntakeVariant(
                name=str(item.get("name") or "unknown"), format="gguf",
                primary_file=str(item.get("primary_file") or ""),
                files=[str(value) for value in item.get("files", [])],
                sharded=bool(item.get("sharded")), size_bytes=size,
                estimated_runtime_gb=estimate, memory_risk=risk, fits_available_ram=fits,
                estimate_note="Estimated as download size × 1.15; context/KV cache and backend overhead can require more memory.",
            ))
        return result

    @classmethod
    def _onnx_variants(cls, files: list[dict], available_gb: float) -> list[IntakeVariant]:
        if not files:
            return []
        known_sizes = [item["size"] for item in files if isinstance(item.get("size"), int)]
        size = sum(known_sizes) if len(known_sizes) == len(files) else None
        estimate, risk, fits = cls._memory_estimate(size, available_gb, 1.35)
        return [IntakeVariant(
            name="ONNX repository files", format="onnx", primary_file=files[0]["name"],
            files=[item["name"] for item in files], sharded=len(files) > 1, size_bytes=size,
            estimated_runtime_gb=estimate, memory_risk=risk, fits_available_ram=fits,
            estimate_note="Estimated as observed ONNX bytes × 1.35. Repository layout and OGA compatibility remain unproven.",
        )]

    @staticmethod
    def _memory_estimate(size_bytes: int | None, available_gb: float, multiplier: float):
        if size_bytes is None:
            return None, "unknown", None
        estimate = round(size_bytes / 1024**3 * multiplier, 2)
        ratio = estimate / max(available_gb, 0.01)
        risk = "low" if ratio <= 0.7 else "moderate" if ratio <= 0.9 else "high"
        return estimate, risk, estimate <= available_gb
