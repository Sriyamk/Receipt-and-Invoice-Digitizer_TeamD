import json
import requests
import re
import cv2
import numpy as np
from paddleocr import PaddleOCR


# ================================
# LOAD OCR MODEL
# ================================
ocr_model = PaddleOCR(use_angle_cls=True, lang='en')


# ================================
# PDF → IMAGE CONVERSION
# ================================
def pdf_to_image(pdf_path):
    """Convert first page of PDF to a cv2 image array."""
    try:
        import fitz
        doc = fitz.open(pdf_path)
        page = doc[0]
        pix = page.get_pixmap(dpi=300)
        img_array = np.frombuffer(pix.tobytes(), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        doc.close()
        return img
    except ImportError:
        print("❌ PyMuPDF not installed. Run: pip install pymupdf")
        return None
    except Exception as e:
        print(f"❌ PDF conversion error: {e}")
        return None


# ================================
# CLEAN OCR TEXT
# Fixes rupee symbol misread as "7" by PaddleOCR
# ================================
def clean_ocr_text(text):
    # Fix "7 48,911.00" → "48,911.00" (rupee misread as 7)
    text = re.sub(r'\b7\s+(\d[\d,]*\.\d{2})', r'\1', text)
    # Remove actual rupee symbols and Rs. which can confuse Mistral
    text = text.replace('₹', '').replace('Rs.', '').replace('Rs', '')
    return text


# ================================
# PARSE PADDLEOCR RESULT
# ================================
def parse_ocr_result(result):
    text = ""
    if not result:
        return text
    try:
        for item in result:
            if isinstance(item, dict) and "rec_texts" in item:
                for t in item["rec_texts"]:
                    text += str(t).strip() + "\n"
            elif isinstance(item, list):
                for word in item:
                    if isinstance(word, (list, tuple)) and len(word) >= 2:
                        part = word[1]
                        if isinstance(part, (list, tuple)) and len(part) >= 1:
                            text += str(part[0]) + "\n"
                        elif isinstance(part, str):
                            text += part + "\n"
    except Exception as e:
        print("OCR PARSE ERROR:", e)
    return text.strip()


# ================================
# OCR FUNCTION
# ================================
def perform_ocr(image_path):
    print(f"\n📄 Reading Invoice: {image_path}")
    if image_path.lower().endswith(".pdf"):
        img = pdf_to_image(image_path)
        if img is None:
            print("❌ Could not convert PDF to image")
            return ""
        result = ocr_model.ocr(img)
    else:
        result = ocr_model.ocr(image_path)

    text = parse_ocr_result(result)
    text = clean_ocr_text(text)
    print("\n🔍 PADDLE OCR TEXT:\n", text)
    return text


# ================================
# TOTAL DETECTION
# ================================
def extract_total_from_keywords(text):
    patterns = [
        r"(TOTAL\s*AMOUNT)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(NET\s*AMOUNT)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(GRAND\s*TOTAL)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(AMOUNT\s*PAYABLE)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(FINAL\s*AMOUNT)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(BILL\s*AMOUNT)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(SUB\s*TOTAL)[^\d]*([\d,]+(?:\.\d{2})?)",
        r"(TOTAL)[^\d]*([\d,]+(?:\.\d{2})?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(2).replace(",", "")
    return None


# ================================
# TAX DETECTION FROM RAW OCR TEXT
#
# FIX 1: Track consumed line indices so CGST and SGST don't
#         both claim the same value when split across lines.
# FIX 2: decimal_pattern now requires digits+decimal (no bare
#         integers like "4") to avoid OCR noise being grabbed.
# FIX 3: Fuzzy SGST matching catches garbled variants like
#         "Outpl Sgst", "SGST @", etc.
# ================================
def extract_tax_from_text(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # FIX 2: strict decimal pattern — must have .XX suffix
    decimal_pattern = re.compile(r"^[\d,]+\.\d{2}$")

    # number_pattern used for split-line detection (also strict now)
    number_pattern = decimal_pattern

    total_label_pattern = re.compile(
        r"(TOTAL|SUBTOTAL|SUB\s*TOTAL|GRAND\s*TOTAL|NET\s*AMOUNT|AMOUNT\s*PAYABLE)",
        re.IGNORECASE
    )

    consumed_indices = set()  # FIX 1: track which line indices are already claimed

    def find_next_number(lines, start_idx):
        """Find the first standalone decimal number within 5 lines after start_idx,
        skipping already-consumed lines."""
        for j in range(start_idx + 1, min(start_idx + 6, len(lines))):
            if j in consumed_indices:
                continue
            if decimal_pattern.match(lines[j]):
                consumed_indices.add(j)
                return lines[j]
        return None

    def find_prev_number(lines, start_idx):
        """Find the first standalone decimal number within 5 lines BEFORE start_idx,
        skipping already-consumed lines. Used for label-after-value layouts."""
        for j in range(start_idx - 1, max(start_idx - 6, -1), -1):
            if j in consumed_indices:
                continue
            if decimal_pattern.match(lines[j]):
                consumed_indices.add(j)
                return lines[j]
        return None

    # Pattern 1: Find CGST and SGST lines (including fuzzy variants).
    # FIX 3: Use broader regex to catch garbled OCR like "Outpl Sgst", "CGST @", etc.
    # FIX 4: For SGST, also try looking BACKWARD (label-after-value layouts like Kakada).
    cgst_val = None
    sgst_val = None

    for i, line in enumerate(lines):
        # Match CGST variants
        if re.search(r'\bCGST\b', line, re.IGNORECASE) and cgst_val is None:
            same = re.search(r"([0-9][0-9,]*\.[0-9]{2})\s*$", line)
            if same:
                cgst_val = same.group(1)
                consumed_indices.add(i)
            else:
                cgst_val = find_next_number(lines, i)

        # FIX 3+4: Match SGST variants including partial/garbled like "Outpl Sgst".
        # Try forward first, then backward (handles label-after-value layouts).
        if re.search(r'SGST', line, re.IGNORECASE) and sgst_val is None:
            same = re.search(r"([0-9][0-9,]*\.[0-9]{2})\s*$", line)
            if same:
                sgst_val = same.group(1)
                consumed_indices.add(i)
            else:
                sgst_val = find_next_number(lines, i)
                if sgst_val is None:
                    # Label came AFTER the value (e.g. "5.24\nOutpl Sgst")
                    sgst_val = find_prev_number(lines, i)

    if cgst_val and sgst_val:
        total_tax = str(round(
            float(cgst_val.replace(",", "")) + float(sgst_val.replace(",", "")), 2
        ))
        print(f"🧾 Tax (CGST+SGST): {total_tax}")
        return total_tax
    if cgst_val:
        # Don't return early — fall through to GST patterns first,
        # CGST-only is a last resort below
        pass

    # Pattern 2: GST on same line or value on line before,
    # skip if total keyword is present on the same line
    for i, line in enumerate(lines):
        if re.match(r"^GST", line, re.IGNORECASE):
            if total_label_pattern.search(line):
                continue
            same = re.search(r"([0-9][0-9,]*\.[0-9]{2})\s*$", line)
            if same:
                print(f"🧾 Tax (GST same-line): {same.group(1)}")
                return same.group(1).replace(",", "")
            if i > 0 and number_pattern.match(lines[i - 1]) and (i - 1) not in consumed_indices:
                print(f"🧾 Tax (split-line GST): {lines[i-1]}")
                return lines[i - 1].replace(",", "")

    # Pattern 3: value on line BEFORE any tax label,
    # skip if two lines above is a total/subtotal label
    tax_label_pattern = re.compile(r"^(CGST|SGST|GST|TAX)", re.IGNORECASE)
    for i, line in enumerate(lines):
        if tax_label_pattern.search(line) and i > 0:
            prev = lines[i - 1]
            if number_pattern.match(prev) and (i - 1) not in consumed_indices:
                if i >= 2 and total_label_pattern.search(lines[i - 2]):
                    continue
                print(f"🧾 Tax (split-line, line before '{line}'): {prev}")
                return prev.replace(",", "")

    # CGST-only fallback (only if no GST found above)
    if cgst_val:
        print(f"🧾 Tax (CGST only): {cgst_val}")
        return cgst_val.replace(",", "")

    return None


# ================================
# MISTRAL EXTRACTION
# ================================
def run_mistral(text):
    if not text or not text.strip():
        print("⚠️  Skipping Mistral — OCR text is empty")
        return {}

    prompt = f"""
You are an invoice data extractor. Extract ONLY these fields from the invoice text.

FIELD DEFINITIONS:
- Vendor: The business/company name only. Pick the clearest single name (e.g. "Kajaria Ceramics"). Do NOT repeat or combine multiple lines.
- Invoice Number: The bill/invoice number. Look for labels like "Bill No", "Invoice No", "Receipt No", "PCSAT".
- Date: The invoice date. Look for labels like "Date:". Format as found.
- Total Amount: The FINAL payable amount. Look for "Total Amount", "Grand Total", "Net Amount", "Amount Payable". Do NOT use Subtotal.
- CGST: CGST tax amount only. Null if not present.
- SGST: SGST tax amount only. Null if not present.
- GST: The GST amount only (the actual tax value on the bill, NOT doubled). Null if not present.

RULES:
- Return ONLY valid JSON. No explanation, no markdown, no extra text.
- If a field is not found, use null.
- Numbers may have commas (e.g. 48,085.00) — extract as-is.
- Vendor must be a SHORT clean name, not a concatenation of multiple lines.
- Invoice Number must be the actual invoice/bill number only, NOT a date or memo number.
- Note: In some bills the value appears on the line BEFORE its label. Read carefully.
- For GST: extract the number literally as it appears on the bill. Do NOT calculate or double it.

{{
  "Vendor": "",
  "Invoice Number": "",
  "Date": "",
  "Total Amount": "",
  "CGST": "",
  "SGST": "",
  "GST": ""
}}

INVOICE TEXT (each line is a separate OCR-detected text block):
{text}
"""

    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0}
    }

    try:
        response = requests.post(url, json=payload, timeout=120)
        raw_output = response.json()["response"]
        print("\n🧠 MISTRAL RAW OUTPUT:\n", raw_output)
        start = raw_output.find("{")
        end = raw_output.rfind("}") + 1
        json_text = raw_output[start:end]
        return json.loads(json_text)
    except requests.exceptions.ConnectionError:
        print("❌ Mistral error — Ollama not running. Start with: ollama serve")
        return {}
    except Exception as e:
        print(f"❌ Mistral extraction error: {e}")
        return {}


# ================================
# CATEGORY CLASSIFICATION
# Separate focused Mistral call — works better than bundling
# with the main extraction prompt on small models.
# ================================

CATEGORY_LIST = [
    "Food & Dining",
    "Travel & Transport",
    "Shopping",
    "Groceries",
    "Electronics",
    "Healthcare",
    "Utilities & Bills",
    "Construction & Hardware",
    "Services",
    "Entertainment",
    "Education",
    "Other"
]

def classify_category(vendor, ocr_text):
    """
    Makes a short, focused Mistral call to classify the bill category.
    Uses vendor name + first 300 chars of OCR text as context.
    Falls back to keyword matching if Mistral fails.
    """

    # ── Keyword fallback (fast, no LLM needed) ──
    KEYWORD_MAP = {
        "Food & Dining":         ["restaurant", "cafe", "hotel", "food", "swiggy", "zomato", "pizza", "biryani", "dhaba", "mess", "canteen", "bakery", "juice"],
        "Travel & Transport":    ["uber", "ola", "rapido", "flight", "airline", "railway", "irctc", "bus", "travel", "petrol", "fuel", "toll", "parking", "cab"],
        "Groceries":             ["grocery", "supermarket", "dmart", "bigbasket", "reliance fresh", "more ", "milk", "vegetable", "kirana"],
        "Electronics":           ["electronics", "mobile", "laptop", "computer", "apple", "samsung", "mi ", "oneplus", "tv ", "camera", "charger", "headphone"],
        "Healthcare":            ["pharmacy", "medical", "hospital", "clinic", "doctor", "diagnostic", "lab", "health", "medicine", "chemist", "apollo", "mg road"],
        "Utilities & Bills":     ["electricity", "water", "gas", "broadband", "internet", "airtel", "jio", "bsnl", "vi ", "recharge", "utility", "tneb", "bescom"],
        "Construction & Hardware":["hardware", "cement", "steel", "tiles", "kajaria", "paint", "plumbing", "pipe", "wire", "electricals", "sanitary", "marble"],
        "Entertainment":         ["cinema", "pvr", "inox", "netflix", "spotify", "game", "amusement", "park", "event", "concert", "ticket"],
        "Education":             ["school", "college", "university", "institute", "tuition", "coaching", "book", "stationery", "course", "exam", "fee"],
        "Shopping":              ["amazon", "flipkart", "myntra", "ajio", "mall", "fashion", "cloth", "shirt", "shoe", "bag", "lifestyle"],
        "Services":              ["salon", "spa", "laundry", "dry clean", "repair", "service", "printing", "courier", "post", "advocate", "ca ", "audit"],
    }

    combined = f"{vendor or ''} {ocr_text[:300]}".lower()

    for category, keywords in KEYWORD_MAP.items():
        if any(kw in combined for kw in keywords):
            print(f"🏷️  Category (keyword match): {category}")
            return category

    # ── LLM fallback for ambiguous bills ──
    prompt = f"""Classify this bill into exactly one category.

Vendor: {vendor or 'Unknown'}
Bill text (first few lines): {ocr_text[:200]}

Categories (choose ONLY one, respond with ONLY the category name, nothing else):
{chr(10).join(CATEGORY_LIST)}"""

    url = "http://127.0.0.1:11434/api/generate"
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 10}
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        raw = response.json()["response"].strip()
        # Match against allowed list (case-insensitive)
        for cat in CATEGORY_LIST:
            if cat.lower() in raw.lower():
                print(f"🏷️  Category (LLM): {cat}")
                return cat
    except Exception as e:
        print(f"⚠️  Category classification error: {e}")

    print("🏷️  Category: defaulting to Other")
    return "Other"


# ================================
# MAIN EXTRACTION FUNCTION
# ================================
def extract_invoice_details(text):
    data = run_mistral(text)

    vendor  = data.get("Vendor")
    invoice = data.get("Invoice Number")
    date    = data.get("Date")

    # Total: prefer Mistral, fall back to regex
    mistral_total = data.get("Total Amount")
    if mistral_total:
        total = str(mistral_total).replace(",", "")
        total = re.sub(r'^7\s*', '', total)  # safety net: strip leading 7 if rupee crept through
    else:
        total = extract_total_from_keywords(text)

    # Tax: always use regex on raw OCR text as source of truth
    tax_from_text = extract_tax_from_text(text)

    if tax_from_text:
        tax = tax_from_text
    else:
        cgst = data.get("CGST")
        sgst = data.get("SGST")
        gst  = data.get("GST")
        try:
            if cgst and sgst:
                tax = str(round(float(str(cgst).replace(",", "")) + float(str(sgst).replace(",", "")), 2))
            elif cgst and not sgst:
                tax = str(cgst).replace(",", "")
            elif gst:
                tax = str(gst).replace(",", "")
            else:
                tax = "N/A"
        except Exception:
            tax = "N/A"

    # Category: dedicated focused call — more reliable than bundling into main prompt
    category = classify_category(vendor, text)

    final_data = {
        "Vendor":         vendor,
        "Invoice Number": invoice,
        "Date":           date,
        "Total Amount":   total,
        "Tax":            tax,
        "Category":       category
    }

    print("\n✅ FINAL EXTRACTED DATA:\n", final_data)
    return final_data