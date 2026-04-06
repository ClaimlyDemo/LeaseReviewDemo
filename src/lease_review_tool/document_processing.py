from __future__ import annotations

import hashlib
import importlib
import re
from pathlib import Path

from .config import Settings, get_settings
from .contracts import ClauseDraft, ParsedDocument, ParsedPage


CLAUSE_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "late_fee": ("late fee", "late charge", "delinquency", "overdue rent"),
    "security_deposit": ("security deposit", "deposit"),
    "entry_rights": ("right of entry", "enter the premises", "access to the premises", "entry"),
    "repair_obligations": ("repair", "maintenance", "maintain", "damages"),
    "utilities": ("utilities", "water", "gas", "electricity", "trash", "sewer"),
    "subletting": ("sublet", "sublease", "assignment", "assign this lease"),
    "early_termination": ("early termination", "terminate this lease"),
    "auto_renewal": ("automatic renewal", "auto-renew", "renewal term"),
    "attorney_fees": ("attorney fees", "attorneys' fees", "legal fees"),
    "arbitration": ("arbitration", "jury trial", "waiver of jury"),
    "default_and_remedies": ("default", "remedy", "breach"),
    "rent_escalation": ("rent increase", "escalation", "increase in rent"),
    "move_out_charges": ("move out", "cleaning fee", "reletting", "surrender"),
    "notice_requirements": ("written notice", "notice shall", "notice must"),
    "guest_limits": ("guest", "occupant"),
    "pet_restrictions": ("pet", "animal"),
}

COMMON_LEASE_TERMS = {
    "agreement",
    "tenant",
    "owner",
    "lease",
    "premises",
    "rent",
    "deposit",
    "term",
    "notice",
    "occupancy",
    "utilities",
    "sublet",
    "assignment",
    "repair",
    "entry",
    "default",
    "remedies",
    "parking",
    "smoking",
    "resident",
    "parking",
    "landlord",
    "written",
    "possession",
    "occupancy",
    "terminate",
    "termination",
    "subletting",
    "pets",
    "animal",
    "vehicle",
    "space",
    "notice",
    "shall",
}

SUSPICIOUS_GLYPHS = set("¡¿¬¦§¨©ª«®¯°±²³´µ¶·¸¹º»¼½¾æøåðþßœƒ")
OCR_REPLACEMENTS = {
    "æ": "ae",
    "Æ": "AE",
    "œ": "oe",
    "Œ": "OE",
    "ø": "o",
    "Ø": "O",
    "å": "a",
    "Å": "A",
    "ð": "d",
    "Ð": "D",
    "þ": "th",
    "Þ": "Th",
    "ƒ": "f",
    "¡": "i",
    "¬": "-",
    "⑆": " ",
    "⑈": " ",
}
BANK_ARTIFACT_TERMS = {
    "washington mutual",
    "wells fargo",
    "non-negotiable",
    "drawer",
    "purchaser copy",
    "issued by",
    "pay to the order",
    "remitter",
    "authorized signature",
    "hold document",
}
FORM_FRAGMENT_PATTERNS = (
    r"^\d+\.\s*(?:name|lrlame|na[mn]e)\s*:\s*.*$",
    r"^[xX]\s*only$",
    r"^[nN]\s*and;?$",
    r"^[eE]\s*only$",
    r"^[iI]\s*and;?$",
    r"^\[\s*\]$",
)


def fingerprint_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_document(path: Path, settings: Settings | None = None) -> ParsedDocument:
    settings = settings or get_settings()
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _parse_pdf(path, settings)
    if suffix == ".docx":
        return _parse_docx(path)
    raise ValueError(f"Unsupported file type: {path.suffix}")


def _parse_pdf(path: Path, settings: Settings) -> ParsedDocument:
    fitz = _require_module("fitz")
    document = fitz.open(str(path))
    textract = _TextractOCR(settings)
    pages: list[ParsedPage] = []

    for index, page in enumerate(document, start=1):
        native_text = _clean_text(_extract_pymupdf_text(page))
        native_quality = _score_text_quality(native_text)
        extraction_method = "pymupdf"
        chosen_text = native_text
        chosen_quality = native_quality
        metadata: dict[str, str | int | float | bool] = {
            "native_quality_score": round(native_quality, 3),
            "ocr_used": False,
        }

        if _should_use_ocr(native_text, native_quality, settings):
            ocr_text = _clean_text(textract.extract_page_text(page))
            ocr_quality = _score_text_quality(ocr_text)
            metadata["ocr_quality_score"] = round(ocr_quality, 3)

            if ocr_quality >= native_quality:
                chosen_text = ocr_text
                chosen_quality = ocr_quality
                extraction_method = "pymupdf+textract"
                metadata["ocr_used"] = True
            else:
                extraction_method = "pymupdf_preferred_over_textract"

        if chosen_text:
            pages.append(
                ParsedPage(
                    page_number=index,
                    text=chosen_text,
                    extraction_method=extraction_method,
                    quality_score=round(chosen_quality, 3),
                    metadata=metadata,
                )
            )

    return ParsedDocument(source_path=path, file_type="pdf", pages=pages)


def _parse_docx(path: Path) -> ParsedDocument:
    docx = _require_module("docx")
    document = docx.Document(str(path))
    paragraphs = [_clean_text(paragraph.text) for paragraph in document.paragraphs]
    text = "\n\n".join(paragraph for paragraph in paragraphs if paragraph)
    return ParsedDocument(
        source_path=path,
        file_type="docx",
        pages=[
            ParsedPage(
                page_number=1,
                text=text,
                extraction_method="docx",
                quality_score=1.0 if text else 0.0,
            )
        ],
    )


def segment_clauses(document: ParsedDocument) -> list[ClauseDraft]:
    clauses: list[ClauseDraft] = []
    clause_index = 1
    for page in document.pages:
        blocks = re.split(r"\n\s*\n+", page.text)
        for block in blocks:
            cleaned = _clean_block_text(block)
            if len(cleaned) < 40:
                continue
            if _should_skip_block(cleaned, page.quality_score or 0.0):
                continue
            clause_type = classify_clause(cleaned)
            extracted_fields = extract_fields(cleaned, clause_type)
            normalized = normalize_clause_text(cleaned, clause_type, extracted_fields)
            clauses.append(
                ClauseDraft(
                    clause_index=clause_index,
                    raw_text=cleaned,
                    clause_type=clause_type,
                    page_start=page.page_number,
                    page_end=page.page_number,
                    source_span=f"page_{page.page_number}_clause_{clause_index}",
                    extracted_fields=extracted_fields,
                    normalized_text=normalized,
                    metadata={
                        "file_type": document.file_type,
                        "extraction_method": page.extraction_method,
                        "page_quality_score": page.quality_score or 0.0,
                    },
                )
            )
            clause_index += 1
    return clauses


def classify_clause(text: str) -> str:
    lowered = text.lower()
    for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return clause_type
    return "other"


def extract_fields(text: str, clause_type: str) -> dict[str, float | int | str | bool]:
    fields: dict[str, float | int | str | bool] = {}
    lowered = text.lower()

    percent_match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if percent_match:
        fields["percent_value"] = float(percent_match.group(1))

    money_match = re.search(r"\$\s?(\d+(?:,\d{3})*(?:\.\d{2})?)", text)
    if money_match:
        fields["amount_usd"] = float(money_match.group(1).replace(",", ""))

    day_match = re.search(r"(\d+)\s+day", lowered)
    if day_match:
        fields["days_value"] = int(day_match.group(1))

    hour_match = re.search(r"(\d+)\s+hour", lowered)
    if hour_match:
        fields["hours_value"] = int(hour_match.group(1))

    if clause_type == "late_fee":
        if "percent_value" in fields:
            fields["late_fee_percent"] = fields["percent_value"]
        if "days_value" in fields:
            fields["grace_period_days"] = fields["days_value"]
        if "amount_usd" in fields:
            fields["late_fee_amount_usd"] = fields["amount_usd"]

    if clause_type == "security_deposit" and "amount_usd" in fields:
        fields["security_deposit_amount_usd"] = fields["amount_usd"]

    if clause_type == "entry_rights":
        if "hours_value" in fields:
            fields["entry_notice_hours"] = fields["hours_value"]
        if "days_value" in fields:
            fields["entry_notice_days"] = fields["days_value"]
        fields["mentions_notice"] = "notice" in lowered

    if clause_type == "auto_renewal" and "days_value" in fields:
        fields["renewal_notice_days"] = fields["days_value"]

    if clause_type == "notice_requirements" and "days_value" in fields:
        fields["notice_days"] = fields["days_value"]

    return fields


def normalize_clause_text(
    raw_text: str,
    clause_type: str,
    extracted_fields: dict[str, float | int | str | bool],
) -> str:
    fields_summary = ", ".join(f"{key}={value}" for key, value in sorted(extracted_fields.items()))
    if fields_summary:
        return f"Clause type: {clause_type}. Extracted fields: {fields_summary}. Clause text: {raw_text}"
    return f"Clause type: {clause_type}. Clause text: {raw_text}"


def _extract_pymupdf_text(page) -> str:
    blocks = page.get_text("blocks", sort=True)
    text_fragments: list[str] = []
    for block in blocks:
        if len(block) < 5:
            continue
        block_text = block[4]
        block_type = int(block[6]) if len(block) > 6 else 0
        if block_type != 0:
            continue
        if not block_text:
            continue
        text_fragments.append(block_text)
    return "\n".join(text_fragments)


def _should_use_ocr(text: str, score: float, settings: Settings) -> bool:
    if len(text.strip()) < 120:
        return True
    if score < settings.pdf_ocr_quality_threshold:
        return True
    return False


def _score_text_quality(text: str) -> float:
    cleaned = text.strip()
    if not cleaned:
        return 0.0

    total_chars = len(cleaned)
    ascii_chars = sum(1 for ch in cleaned if ch in "\n\t" or 32 <= ord(ch) <= 126)
    ascii_ratio = ascii_chars / total_chars

    suspicious_glyph_ratio = sum(1 for ch in cleaned if ch in SUSPICIOUS_GLYPHS) / total_chars

    alpha_tokens = re.findall(r"[A-Za-z]{3,}", cleaned)
    if not alpha_tokens:
        return max(0.0, ascii_ratio - suspicious_glyph_ratio)

    weird_case_ratio = sum(1 for token in alpha_tokens if _is_weird_case_token(token)) / len(alpha_tokens)
    long_tokens = [token for token in alpha_tokens if len(token) >= 6]
    no_vowel_ratio = (
        sum(1 for token in long_tokens if not re.search(r"[aeiouy]", token.lower())) / len(long_tokens)
        if long_tokens
        else 0.0
    )
    lowered = cleaned.lower()
    lease_term_hits = sum(1 for term in COMMON_LEASE_TERMS if term in lowered)
    lease_signal = min(1.0, lease_term_hits / 8)

    score = (
        0.40 * ascii_ratio
        + 0.25 * (1.0 - min(1.0, suspicious_glyph_ratio * 8))
        + 0.20 * (1.0 - min(1.0, weird_case_ratio * 2.5))
        + 0.15 * lease_signal
        - 0.15 * no_vowel_ratio
    )
    return max(0.0, min(1.0, score))


def _is_weird_case_token(token: str) -> bool:
    if len(token) < 6:
        return False
    if token.islower() or token.isupper() or token.istitle():
        return False
    transitions = sum(1 for left, right in zip(token, token[1:]) if left.islower() != right.islower())
    return transitions >= 3


def _clean_text(text: str) -> str:
    normalized = text.replace("\x00", " ")
    for source, replacement in OCR_REPLACEMENTS.items():
        normalized = normalized.replace(source, replacement)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\r\n?", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _clean_block_text(text: str) -> str:
    normalized = _clean_text(text)
    lines = [line.strip(" |") for line in normalized.splitlines()]
    cleaned_lines: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if _is_low_value_line(line):
            continue
        cleaned_lines.append(line)
    normalized = "\n".join(cleaned_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


class _TextractOCR:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None

    def extract_page_text(self, page) -> str:
        client = self._get_client()
        pixmap = page.get_pixmap(dpi=self.settings.pdf_ocr_render_dpi, alpha=False)
        image_bytes = pixmap.tobytes("png")
        page_number = int(page.number) + 1

        try:
            response = client.detect_document_text(Document={"Bytes": image_bytes})
        except Exception as exc:
            raise RuntimeError(self._format_textract_error(exc, page_number, len(image_bytes))) from exc

        lines = []
        for block in response.get("Blocks", []):
            if block.get("BlockType") != "LINE":
                continue
            if not block.get("Text"):
                continue
            bbox = block.get("Geometry", {}).get("BoundingBox", {})
            lines.append(
                (
                    float(bbox.get("Top", 0.0)),
                    float(bbox.get("Left", 0.0)),
                    block["Text"],
                )
            )

        lines.sort(key=lambda item: (item[0], item[1]))
        return "\n".join(text for _, _, text in lines)

    def _get_client(self):
        if self._client is not None:
            return self._client

        boto3 = _require_module("boto3")
        session_kwargs = {}
        if self.settings.aws_region:
            session_kwargs["region_name"] = self.settings.aws_region

        session = boto3.session.Session(**session_kwargs)
        self._client = session.client("textract")
        return self._client

    def _format_textract_error(self, exc: Exception, page_number: int, byte_size: int) -> str:
        code = None
        message = str(exc) or exc.__class__.__name__

        try:
            from botocore.exceptions import ClientError

            if isinstance(exc, ClientError):
                error = exc.response.get("Error", {})
                code = error.get("Code")
                message = error.get("Message") or message
        except Exception:
            pass

        details = [
            f"page={page_number}",
            f"region={self.settings.aws_region or 'unset'}",
            f"image_bytes={byte_size}",
        ]
        if code:
            details.append(f"aws_code={code}")

        return f"AWS Textract OCR failed ({', '.join(details)}): {message}"


def _require_module(name: str):
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise RuntimeError(
            f"Missing dependency '{name}'. Install project dependencies before running this stage."
        ) from exc


def _is_low_value_line(line: str) -> bool:
    lowered = line.lower().strip()
    if any(re.match(pattern, lowered) for pattern in FORM_FRAGMENT_PATTERNS):
        return True
    words = re.findall(r"[a-zA-Z]+", lowered)
    if len(words) <= 2 and any(token in lowered for token in {"only", "and", "name"}):
        return True
    if re.fullmatch(r"[\W\d_]+", lowered):
        return True
    return False


def _should_skip_block(text: str, page_quality: float) -> bool:
    lowered = text.lower()
    if _looks_like_bank_artifact(lowered):
        return True
    if _looks_like_form_fragment(text):
        return True
    if _text_is_too_noisy(text, page_quality):
        return True
    return False


def _looks_like_bank_artifact(lowered: str) -> bool:
    hit_count = sum(1 for term in BANK_ARTIFACT_TERMS if term in lowered)
    digit_count = sum(1 for ch in lowered if ch.isdigit())
    return hit_count >= 2 or (hit_count >= 1 and digit_count >= 20)


def _looks_like_form_fragment(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return True

    short_lines = sum(1 for line in lines if len(re.findall(r"[A-Za-z]+", line)) <= 2)
    checkbox_hits = sum(
        1
        for line in lines
        if any(re.match(pattern, line.lower()) for pattern in FORM_FRAGMENT_PATTERNS)
    )
    if checkbox_hits >= 2 and short_lines >= max(2, len(lines) // 2):
        return True

    if len(lines) <= 6:
        alpha_tokens = re.findall(r"[A-Za-z]{3,}", text)
        lease_hits = sum(1 for term in COMMON_LEASE_TERMS if term in text.lower())
        if len(alpha_tokens) < 10 and lease_hits <= 1:
            return True

    return False


def _text_is_too_noisy(text: str, page_quality: float) -> bool:
    lowered = text.lower()
    alpha_tokens = re.findall(r"[A-Za-z]{3,}", text)
    if not alpha_tokens:
        return True

    suspicious_ratio = sum(1 for ch in text if ch in SUSPICIOUS_GLYPHS) / max(1, len(text))
    lease_hits = sum(1 for term in COMMON_LEASE_TERMS if term in lowered)
    weird_case_ratio = sum(1 for token in alpha_tokens if _is_weird_case_token(token)) / max(1, len(alpha_tokens))

    if page_quality < 0.45 and lease_hits <= 1:
        return True
    if suspicious_ratio > 0.03 and lease_hits <= 2:
        return True
    if weird_case_ratio > 0.25 and lease_hits <= 2:
        return True
    return False
