"""
title: Vision + NMR Strict Mode Filter
author: Haron Admin
author_url: https://webui.glchemtec.ca
funding_url: https://webui.glchemtec.ca
version: 2.0
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


NMR_STRICT_BLOCK = """
[NMR STRICT MODE — MUST FOLLOW][CRITICAL NMR OCR MODE – ZERO TOLERANCE FOR ERRORS]
You are performing STRICT OCR (Optical Character Recognition) on NMR spectrum peak labels.

YOUR ONLY TASK: Read the printed numeric labels EXACTLY as they appear.

ABSOLUTE RULES:
1) Read EVERY digit character-by-character from the image labels
2) If label shows "164.15" → write "164.15" (NOT 164.23, 164.2, or 164)
3) If label shows "160.87" → write "160.87" (NOT 161.88, 160.9, or 161)
4) Preserve ALL decimal places EXACTLY as printed
5) DO NOT round, adjust, normalize, or "fix" any values
6) DO NOT estimate based on peak visual position on the spectrum
7) DO NOT interpolate between grid lines
8) DO NOT use "nearby" or "approximate" values

WHAT YOU MUST DO:
✓ Read text labels with character-level precision
✓ Double-check EVERY number before reporting
✓ If unsure about ANY digit, mark as "UNREADABLE" instead of guessing

WHAT YOU MUST NEVER DO:
❌ Visual estimation from peak position
❌ Rounding to "cleaner" numbers  
❌ Approximating based on grid lines
❌ Inferring values between labeled peaks
❌ Adjusting values to match expected chemical shifts

CRITICAL OUTPUT REQUIREMENTS:
1) ALWAYS produce this table first (MANDATORY):
   | Peak# | δ (ppm) | Mult. | J (Hz) | Int. | Assignment |

2) δ (ppm) values MUST match spectrum labels EXACTLY.
   - Your previous attempts had 0.1-1.5 ppm OCR errors
   - This is UNACCEPTABLE for scientific data
   - EVERY value must be pixel-perfect OCR transcription

3) Solvent/reference handling:
   - Label solvent/reference peaks in the table
   - EXCLUDE solvent/reference peaks from the ACS δ summary

4) After the table, ALWAYS include:
   - ACS-style δ summary (excluding solvent/reference)
   - Interpretation (clearly separate FACT vs INFERENCE)
   - Data quality & limitations
   - Confidence rating (HIGH/MEDIUM/LOW)

MANDATORY FINAL SELF-AUDIT:
Before finalizing, re-check EVERY δ value against the spectrum labels.
If any mismatch exists, correct it or mark UNREADABLE.
Treat this like a medical transcription where errors have serious consequences.

[/NMR STRICT MODE]
""".strip()


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for filter operations."
        )
        detail_mode: str = Field(
            default="high",
            description="Vision detail mode: 'low', 'high', or 'auto'. Use 'high' for NMR labels.",
        )
        enable_nmr_router: bool = Field(
            default=True,
            description="If true, injects NMR strict instructions when NMR is detected.",
        )

        # Keywords that strongly indicate NMR context
        nmr_keywords: str = Field(
            default="nmr,1h,¹h,13c,¹³c,dept,hsqc,hmbc,ppm,cdcl3,cdcl₃,dmsod6,dmso-d6,spectrum",
            description="Comma-separated keywords used to detect NMR intent.",
        )

    def __init__(self):
        self.valves = self.Valves()
        print("[VISION-NMR-STRICT] Filter initialized - detail=high, NMR strict mode enabled")

    # -------------------------
    # Helpers
    # -------------------------
    def _log(self, msg: str) -> None:
        print(f"[VISION-NMR-STRICT] {msg}")

    def _is_image_item(self, item: Any) -> bool:
        return isinstance(item, dict) and item.get("type") in (
            "image_url",
            "input_image",
        )

    def _force_high_detail(self, item: dict) -> None:
        # Normalize common image payload shapes and set detail
        if "image_url" in item:
            img = item["image_url"]
            if isinstance(img, dict):
                img["detail"] = self.valves.detail_mode
            elif isinstance(img, str):
                item["image_url"] = {"url": img, "detail": self.valves.detail_mode}
            return

        if "url" in item and isinstance(item["url"], str):
            url = item["url"]
            item.pop("url", None)
            item["image_url"] = {"url": url, "detail": self.valves.detail_mode}

    def _extract_text_from_messages(self, messages: Any) -> str:
        # Pull user-visible text to detect NMR intent
        parts = []
        if not isinstance(messages, list):
            return ""

        for msg in messages:
            if not isinstance(msg, dict):
                continue
            content = msg.get("content")
            if isinstance(content, str):
                parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        t = item.get("text")
                        if isinstance(t, str):
                            parts.append(t)
        return "\n".join(parts)

    def _detect_nmr(self, body: dict) -> bool:
        # NMR detected if:
        # - any NMR keywords appear in user text OR
        # - there is an image AND nearby text contains ppm / 13C / 1H etc.
        messages = body.get("messages")
        # CRITICAL: Only check LAST user message, not entire history
        last_user_msg = None
        if isinstance(messages, list):
            for msg in reversed(messages):
                if isinstance(msg, dict) and msg.get("role") == "user":
                    last_user_msg = msg
                    break

        if not last_user_msg:
            return False

        text = self._extract_text_from_messages([last_user_msg]).lower()
        kw = [
            k.strip().lower() for k in self.valves.nmr_keywords.split(",") if k.strip()
        ]
        keyword_hit = any(k in text for k in kw)

        # Also treat as NMR if user explicitly says "spectrum" + image exists
        has_image = False
        if isinstance(messages, list):
            for msg in messages:
                content = msg.get("content")
                if isinstance(content, list):
                    for item in content:
                        if self._is_image_item(item):
                            has_image = True
                            break
                if has_image:
                    break

        return bool(keyword_hit and has_image) or (
            has_image
            and ("ppm" in text or "13c" in text or "¹³c" in text or "nmr" in text)
        )

    def _inject_strict_block(self, body: dict) -> None:
        """
        Inject NMR_STRICT_BLOCK into the last user message in a safe way.
        If there is no user message, add a system message at the front.
        """
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            body["messages"] = [{"role": "system", "content": NMR_STRICT_BLOCK}]
            return

        # Find last user message
        last_user_idx = None
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], dict) and messages[i].get("role") == "user":
                last_user_idx = i
                break

        if last_user_idx is None:
            # Prepend system instruction
            messages.insert(0, {"role": "system", "content": NMR_STRICT_BLOCK})
            return

        msg = messages[last_user_idx]
        content = msg.get("content")

        # If content is string, append block
        if isinstance(content, str):
            if NMR_STRICT_BLOCK not in content:
                msg["content"] = content.rstrip() + "\n\n" + NMR_STRICT_BLOCK
            return

        # If content is list, add a text item at start (highest priority)
        if isinstance(content, list):
            # avoid duplicates
            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ):
                    if "[NMR STRICT MODE" in item.get("text"):
                        return
            content.insert(0, {"type": "text", "text": NMR_STRICT_BLOCK})
            return

    # -------------------------
    # Main entry
    # -------------------------
    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        if not isinstance(body, dict):
            return body

        images_found = 0
        nmr_detected = False

        # 1) Force high detail on all image items
        messages = body.get("messages")
        if isinstance(messages, list):
            for msg in messages:
                if not isinstance(msg, dict):
                    continue
                content = msg.get("content")
                if isinstance(content, list):
                    for item in content:
                        if self._is_image_item(item):
                            self._force_high_detail(item)
                            images_found += 1

        # 2) If NMR detected, inject strict NMR instruction block
        if self.valves.enable_nmr_router and self._detect_nmr(body):
            nmr_detected = True
            self._inject_strict_block(body)
            self._log(f"🔬 NMR STRICT MODE ACTIVATED - {images_found} image(s) set to detail=high")
        elif images_found > 0:
            self._log(f"📷 {images_found} image(s) set to detail={self.valves.detail_mode}")

        return body
