import pytesseract
import cv2
import re
import os
import subprocess
import json

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# ================================
# OCR FUNCTION
# ================================
def perform_ocr(image_path):

    abs_path = os.path.abspath(image_path)
    print("\n📄 Reading Invoice:", abs_path)

    img = cv2.imread(abs_path)

    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.threshold(gray,150,255,cv2.THRESH_BINARY)[1]

    text = pytesseract.image_to_string(gray, config='--oem 3 --psm 6')

    print("\n🔍 RAW OCR TEXT:\n", text)

    return text


# ================================
# GEMMA FUNCTION
# ================================
def run_gemma(text):

    prompt = f"""
Extract the following from invoice text and return JSON only:

Vendor
Invoice Number
Date
Total Amount
Tax

Invoice Text:
{text}
"""

    try:
        result = subprocess.run(
            ["C:\\Users\\atulc\\AppData\\Local\\Programs\\Ollama\\ollama.exe","run","gemma:2b"],
            input=prompt.encode('utf-8'),
            capture_output=True
        )

        output = result.stdout.decode('utf-8','ignore')

        print("\n🤖 GEMMA OUTPUT:\n", output)

        json_text = re.search(r'\{.*\}', output, re.DOTALL)

        if json_text:
            return json.loads(json_text.group())

    except Exception as e:
        print("❌ GEMMA ERROR:",e)

    return {}



# ================================
# MAIN EXTRACTION
# ================================
def extract_invoice_details(text):

    # Fix OCR number error
    text = re.sub(r'(\d+)\s+(\d{2})', r'\1.\2', text)

    data = run_gemma(text)

    # -------------------------
    # DATE FALLBACK
    # -------------------------
    if not data.get("Date"):

        date_match = re.search(
            r'\d{2}[/-]\d{2}[/-]\d{2,4}',
            text
        )

        if date_match:
            data["Date"] = date_match.group()


    # -------------------------
    # TOTAL FALLBACK
    # Prefer TOTAL over SUBTOTAL
    # -------------------------
    if not data.get("Total Amount"):

        total_match = re.search(
            r'(total amount|grand total|total)[^\d£$₹]{0,20}[£$₹]?\s*(\d+\.\d{2})',
            text,
            re.IGNORECASE
        )

        if total_match:
            data["Total Amount"] = total_match.group(2)


    # -------------------------
    # TAX FALLBACK
    # Handles TAX (20%) : 69.00
    # -------------------------
    if not data.get("Tax"):

        tax_match = re.search(
            r'(tax|gst)[^\d£$₹]{0,20}(?:\(\d+%\))?[^\d£$₹]{0,10}[£$₹]?\s*(\d+\.\d{2})',
            text,
            re.IGNORECASE
        )

        if tax_match:
            data["Tax"] = tax_match.group(2)


    print("\n✅ FINAL EXTRACTED DATA:\n",data)

    return {
        "Vendor": data.get("Vendor"),
        "Invoice Number": data.get("Invoice Number"),
        "Date": data.get("Date"),
        "Total Amount": data.get("Total Amount"),
        "Tax": data.get("Tax")
    }
