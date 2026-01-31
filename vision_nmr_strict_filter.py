"""
title: Vision + NMR Strict Mode Filter
author: Haron Admin
author_url: https://webui.glchemtec.ca
funding_url: https://webui.glchemtec.ca
version: 3.0
description: Forces high-detail vision mode and injects strict NMR OCR instructions for accurate spectrum analysis. Supports 1D/2D NMR for organic chemistry.
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


NMR_STRICT_BLOCK = """
[NMR STRICT MODE — MANDATORY FOR ALL SPECTRUM ANALYSIS]

═══════════════════════════════════════════════════════════════
PART 1: CRITICAL OCR RULES (ZERO TOLERANCE FOR ERRORS)
═══════════════════════════════════════════════════════════════

You are performing STRICT OCR on NMR spectrum peak labels.
This is scientific data - errors have serious consequences.

ABSOLUTE RULES FOR READING PEAK LABELS:
1) Read EVERY digit character-by-character: 1-6-4-.-1-5 = 164.15
2) If label shows "164.15" → write "164.15" (NOT 164.2, 164.23, or 164)
3) If label shows "7.26" → write "7.26" (NOT 7.3 or 7.25)
4) Preserve ALL decimal places EXACTLY as printed
5) DO NOT round, adjust, normalize, or "fix" any values
6) DO NOT estimate from peak visual position on the axis
7) DO NOT interpolate between grid lines
8) If ANY digit is unclear → write "UNREADABLE" not your guess

FORBIDDEN ACTIONS:
❌ Rounding 77.03 → 77.0
❌ "Correcting" 164.15 → 164.13 
❌ Estimating unlabeled peaks from position
❌ Merging close peaks into one value
❌ Dropping peaks that seem like noise
❌ Adding peaks you think should exist

═══════════════════════════════════════════════════════════════
PART 2: SPECTRUM TYPE IDENTIFICATION
═══════════════════════════════════════════════════════════════

FIRST, identify the spectrum type from axis labels and range:

1D NMR:
• ¹H NMR: δ 0-14 ppm (typically 0-12), look for TMS at 0 ppm
• ¹³C NMR: δ 0-220 ppm, CDCl₃ triplet ~77 ppm
• ¹³C DEPT-135: CH₃/CH up, CH₂ down, quaternary C absent
• ¹³C DEPT-90: Only CH carbons visible
• ¹³C APT: CH₃/CH vs CH₂/quaternary C differentiated
• ¹⁹F NMR: δ +100 to -300 ppm (CFCl₃ reference at 0)
• ³¹P NMR: δ +250 to -250 ppm (H₃PO₄ reference at 0)
• ¹¹B NMR: δ +100 to -100 ppm

2D NMR:
• COSY (¹H-¹H): Square plot, diagonal + cross-peaks show J-coupling
• HSQC (¹H-¹³C): ¹H on one axis, ¹³C on other, direct C-H bonds
• HMBC (¹H-¹³C): Long-range C-H correlations (2-4 bonds)
• NOESY/ROESY: Through-space correlations (< 5 Å)
• TOCSY: Spin system identification

═══════════════════════════════════════════════════════════════
PART 3: OUTPUT FORMAT (MANDATORY)
═══════════════════════════════════════════════════════════════

FOR 1D ¹H NMR - ALWAYS USE THIS TABLE:
| Peak# | δ (ppm) | Multiplicity | J (Hz) | Integration | Assignment |
|-------|---------|--------------|--------|-------------|------------|
| 1     | 7.26    | s            | -      | 1H (solvent)| CHCl₃      |
| 2     | 7.45    | dd           | 8.2, 1.5 | 2H        | Ar-H       |

Multiplicity codes: s=singlet, d=doublet, t=triplet, q=quartet, 
                    m=multiplet, dd=doublet of doublets, dt=doublet of triplets,
                    br=broad, app=apparent

FOR 1D ¹³C NMR - USE THIS TABLE:
| Peak# | δ (ppm) | DEPT info | Assignment |
|-------|---------|-----------|------------|
| 1     | 77.16   | (solvent) | CDCl₃      |
| 2     | 170.25  | C         | C=O        |
| 3     | 128.45  | CH        | Ar-CH      |

FOR 2D NMR - LIST CORRELATIONS:
| ¹H (ppm) | ¹³C (ppm) | Correlation Type | Assignment |
|----------|-----------|------------------|------------|
| 7.45     | 128.5     | HSQC (direct)    | Ar-CH      |
| 7.45     | 170.2     | HMBC (3-bond)    | H→C=O      |

═══════════════════════════════════════════════════════════════
PART 4: COMMON SOLVENTS & REFERENCES (EXCLUDE FROM COMPOUND DATA)
═══════════════════════════════════════════════════════════════

ALWAYS identify and EXCLUDE these from compound peak lists:

¹H NMR Solvents:
• CDCl₃: δ 7.26 (s)
• DMSO-d₆: δ 2.50 (quintet)
• D₂O: δ 4.79
• CD₃OD: δ 3.31 (quintet), 4.87 (s)
• Acetone-d₆: δ 2.05 (quintet)
• C₆D₆: δ 7.16 (s)
• TMS: δ 0.00 (s) - reference

¹³C NMR Solvents:
• CDCl₃: δ 77.16 (triplet, may show as 77.0, 77.2, 77.4)
• DMSO-d₆: δ 39.52 (septet)
• CD₃OD: δ 49.00 (septet)
• Acetone-d₆: δ 29.84 (septet), 206.26 (s)
• C₆D₆: δ 128.06 (triplet)

═══════════════════════════════════════════════════════════════
PART 5: FINAL OUTPUT REQUIREMENTS
═══════════════════════════════════════════════════════════════

ALWAYS PROVIDE (in this order):

1) SPECTRUM IDENTIFICATION
   - Nucleus (¹H, ¹³C, etc.)
   - Experiment type (1D, DEPT, COSY, HSQC, etc.)
   - Solvent identified
   - Spectrometer frequency (if visible, e.g., "400 MHz")
   - Data quality assessment

2) COMPLETE PEAK TABLE (as shown above)
   - ALL labeled peaks transcribed EXACTLY
   - Solvent/reference peaks marked but included
   - UNREADABLE for any unclear values

3) ACS-STYLE SUMMARY (compound peaks only, exclude solvent):
   ¹H NMR (400 MHz, CDCl₃): δ 7.45 (dd, J = 8.2, 1.5 Hz, 2H), 7.32 (t, J = 7.5 Hz, 1H), ...
   ¹³C NMR (100 MHz, CDCl₃): δ 170.2, 136.5, 128.4, ...

4) STRUCTURAL INTERPRETATION
   - Clearly separate OBSERVED FACTS vs INFERENCES
   - Functional groups suggested by chemical shift ranges
   - If structure provided: correlate peaks to structure
   - If no structure: suggest possible structural features

5) CONFIDENCE & LIMITATIONS
   - HIGH: All peaks clearly readable, consistent data
   - MEDIUM: Some peaks unclear, minor ambiguities
   - LOW: Poor image quality, many unreadable values
   - List specific limitations

═══════════════════════════════════════════════════════════════
MANDATORY SELF-AUDIT BEFORE SUBMITTING
═══════════════════════════════════════════════════════════════

Before finalizing your response:
□ Re-check EVERY δ value against the spectrum image
□ Verify decimal places match EXACTLY
□ Confirm no peaks were missed or added
□ Ensure solvent peaks are identified and excluded from ACS summary
□ If ANY doubt about a value → mark UNREADABLE

This is scientific data used for research and publications.
Accuracy is mandatory. When in doubt, say "UNREADABLE".

[/NMR STRICT MODE]
""".strip()


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=0, description="Priority level for filter operations (0 = highest, runs first)."
        )
        detail_mode: str = Field(
            default="high",
            description="Vision detail mode: 'low', 'high', or 'auto'. Use 'high' for NMR labels.",
        )
        enable_nmr_router: bool = Field(
            default=True,
            description="If true, injects NMR strict instructions when NMR is detected.",
        )
        # Keywords that strongly indicate NMR context - expanded for organic chemistry
        nmr_keywords: str = Field(
            default="nmr,1h,13c,19f,31p,11b,dept,dept-135,dept-90,apt,hsqc,hmbc,hmqc,cosy,noesy,roesy,tocsy,inadequate,ppm,cdcl3,dmso-d6,dmsod6,cd3od,d2o,c6d6,tms,spectrum,spectra,chemical shift,coupling,multiplet,singlet,doublet,triplet,quartet",
            description="Comma-separated keywords used to detect NMR intent.",
        )

    def __init__(self):
        self.valves = self.Valves()
        print("[VISION-NMR-STRICT] Filter v3.0 initialized - detail=high, comprehensive NMR support enabled")

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
        """Force high detail mode on image items for accurate OCR."""
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
        """Pull user-visible text to detect NMR intent."""
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
        """
        Detect if the request is NMR-related.
        Returns True if NMR keywords found AND image present.
        """
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

        # Check if there's an image in the conversation
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

        # NMR mode activates if: (keyword + image) OR (image + specific NMR terms)
        specific_nmr_terms = ["ppm", "13c", "1h", "nmr", "spectrum", "spectra", 
                             "dept", "cosy", "hsqc", "hmbc", "noesy", "chemical shift"]
        has_specific_term = any(term in text for term in specific_nmr_terms)
        
        return bool(keyword_hit and has_image) or (has_image and has_specific_term)

    def _inject_strict_block(self, body: dict) -> None:
        """
        Inject NMR_STRICT_BLOCK into the last user message.
        Places instructions BEFORE the user's text for highest priority.
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

        # If content is string, prepend block (instructions first!)
        if isinstance(content, str):
            if "[NMR STRICT MODE" not in content:
                msg["content"] = NMR_STRICT_BLOCK + "\n\n" + content
            return

        # If content is list, add a text item at START (highest priority)
        if isinstance(content, list):
            # Check for duplicates
            for item in content:
                if (
                    isinstance(item, dict)
                    and item.get("type") == "text"
                    and isinstance(item.get("text"), str)
                ):
                    if "[NMR STRICT MODE" in item.get("text"):
                        return
            # Insert at beginning for highest priority
            content.insert(0, {"type": "text", "text": NMR_STRICT_BLOCK})
            return

    # -------------------------
    # Main entry
    # -------------------------
    def inlet(self, body: dict, __user__: Optional[dict] = None) -> dict:
        """
        Main filter entry point.
        1) Forces detail=high on all images
        2) Injects NMR strict instructions when NMR detected
        """
        if not isinstance(body, dict):
            return body

        images_found = 0
        nmr_detected = False

        # 1) Force high detail on ALL image items (always, not just NMR)
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
            self._log(f"NMR STRICT MODE ACTIVATED - {images_found} image(s) with detail=high")
        elif images_found > 0:
            self._log(f"{images_found} image(s) set to detail={self.valves.detail_mode}")

        return body
