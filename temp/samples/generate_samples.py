"""Generate demo document bundles for DocVerify.

Creates two cases under samples/:
  clean/  — genuine applicant Ramesh Kumar; everything is consistent.
  fraud/  — applicant Suresh Patel; salary inflated 2x vs bank statement,
            land deed for someone else's survey number, backdated and
            re-exported through Photoshop, plus a tampered deed photo
            with a pasted seal for the ELA demo.

Run with:  uv run python samples/generate_samples.py
"""

from __future__ import annotations

import io
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz
from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

SAMPLES = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc)


def _pdf(lines: list[tuple[str, str, float]], title: str) -> bytes:
    """Render (font, text, size) lines down an A4 page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4
    c.setFont("Helvetica-Bold", 14)
    c.drawString(60, height - 70, title)
    y = height - 110
    for font, text, size in lines:
        c.setFont(font, size)
        c.drawString(60, y, text)
        y -= size + 9
    c.save()
    return buf.getvalue()


def _stamp_metadata(payload: bytes, *, producer: str, creator: str,
                    created: datetime, modified: datetime | None = None) -> bytes:
    def fmt(dt: datetime) -> str:
        return dt.strftime("D:%Y%m%d%H%M%S+00'00'")

    doc = fitz.open(stream=payload, filetype="pdf")
    doc.set_metadata({
        "producer": producer,
        "creator": creator,
        "creationDate": fmt(created),
        "modDate": fmt(modified or created),
    })
    out = doc.tobytes()
    doc.close()
    return out


def salary_slip(name: str, pan: str, cin: str, net_pay: str,
                tampered_amount_font: bool) -> bytes:
    body = "Helvetica"
    amount_font = "Courier-Bold" if tampered_amount_font else body
    lines = [
        (body, "TechNova Solutions Pvt Ltd" if not tampered_amount_font
               else "Sunrise Trading Pvt Ltd", 10),
        (body, f"CIN: {cin}", 10),
        (body, f"Employee Name: {name}", 10),
        (body, f"PAN: {pan}", 10),
        (body, "Designation: Senior Engineer    Pay period: May 2026", 10),
        (body, "Address: 14 MG Road, Indiranagar, Bengaluru 560038", 10),
        (body, "Earnings", 10),
        (body, "Basic Pay: 50,000.00      HRA: 20,000.00", 10),
        (body, "Special Allowance: 14,000.00     Deductions (PF/Tax): 4,000.00", 10),
        (amount_font, f"Net Pay: Rs. {net_pay}", 10),
        (body, "This is a system generated salary slip and does not require a signature.", 9),
    ]
    return _pdf(lines, "SALARY SLIP - MAY 2026")


def bank_statement(name: str, pan: str, credit: str) -> bytes:
    months = ["01-03-2026", "01-04-2026", "01-05-2026"]
    lines = [
        ("Helvetica", "Canara Bank - Statement of Account", 10),
        ("Helvetica", f"Account Holder: {name}", 10),
        ("Helvetica", f"PAN: {pan}", 10),
        ("Helvetica", "Address: 14 MG Road, Indiranagar, Bengaluru 560038", 10),
        ("Helvetica", "Opening Balance: 1,10,000.00", 10),
        ("Helvetica", "Date           Description                      Amount      Type", 10),
    ]
    for m in months:
        lines.append(("Helvetica", f"{m}    SALARY CREDIT TECHNOVA NEFT     {credit}   CR", 10))
        lines.append(("Helvetica", f"{m}    RENT PAYMENT IMPS               18,000.00   DR", 10))
    lines.append(("Helvetica", "Closing Balance: 1,94,000.00", 10))
    return _pdf(lines, "STATEMENT OF ACCOUNT - MAR TO MAY 2026")


def land_deed(owner: str, survey_no: str, reg_date: str) -> bytes:
    lines = [
        ("Helvetica", "Office of the Sub-Registrar, Devanahalli", 10),
        ("Helvetica", f"Owner Name: {owner}", 10),
        ("Helvetica", f"Survey Number: {survey_no}", 10),
        ("Helvetica", "Village: Devanahalli    District: Bengaluru Rural", 10),
        ("Helvetica", f"Registration Date: {reg_date}", 10),
        ("Helvetica", "Extent: 1.2 acres    Classification: Agricultural", 10),
        ("Helvetica", "Schedule of Property: bounded north by survey 142/1,", 10),
        ("Helvetica", "south by village road, east by survey 142/3.", 10),
        ("Helvetica", "Encumbrance: Nil as on date of registration.", 10),
    ]
    return _pdf(lines, "SALE DEED - CERTIFIED EXTRACT")


def tampered_photo() -> bytes:
    """A 'photo of a deed' where a seal was pasted in after JPEG capture."""
    rng = random.Random(7)
    w, h = 900, 640
    img = Image.new("RGB", (w, h), (214, 205, 186))
    draw = ImageDraw.Draw(img)
    # Paper texture: noise + ruled text lines, like a photographed document.
    for _ in range(22000):
        x, y = rng.randrange(w), rng.randrange(h)
        g = rng.randrange(-18, 18)
        base = img.getpixel((x, y))
        img.putpixel((x, y), tuple(max(0, min(255, c + g)) for c in base))
    for i, y in enumerate(range(90, 560, 34)):
        draw.line([(70, y), (830 - (i % 4) * 60, y)], fill=(82, 70, 58), width=3)
    draw.text((70, 40), "SALE DEED  -  SURVEY NO 142/2A", fill=(40, 32, 25))

    # Simulate the camera's JPEG pass.
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=68)
    buf.seek(0)
    img = Image.open(buf).convert("RGB")

    # Paste a pristine, never-compressed 'government seal' on top.
    draw = ImageDraw.Draw(img)
    cx, cy, r = 700, 480, 70
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(235, 240, 248),
                 outline=(120, 20, 30), width=6)
    draw.ellipse([cx - r + 16, cy - r + 16, cx + r - 16, cy + r - 16],
                 outline=(120, 20, 30), width=3)
    draw.text((cx - 42, cy - 8), "REGISTERED", fill=(120, 20, 30))

    out = io.BytesIO()
    img.save(out, "JPEG", quality=95)
    return out.getvalue()


def main() -> None:
    clean = SAMPLES / "clean"
    fraud = SAMPLES / "fraud"
    clean.mkdir(exist_ok=True)
    fraud.mkdir(exist_ok=True)

    issued_2019 = datetime(2019, 3, 20, 11, 0, tzinfo=timezone.utc)
    last_month = NOW - timedelta(days=20)
    two_days_ago = NOW - timedelta(days=2)

    # --- Clean bundle: Ramesh Kumar, everything consistent.
    (clean / "salary_slip.pdf").write_bytes(_stamp_metadata(
        salary_slip("Ramesh Kumar", "ABCPK1234F", "U72200KA2015PTC081234",
                    "80,000.00", tampered_amount_font=False),
        producer="TechNova Payroll System v4.2", creator="TechNova HRMS",
        created=last_month))
    (clean / "bank_statement.pdf").write_bytes(_stamp_metadata(
        bank_statement("Ramesh Kumar", "ABCPK1234F", "80,000.00"),
        producer="Canara Bank e-Statement Service", creator="Canara Bank",
        created=last_month))
    (clean / "land_record.pdf").write_bytes(_stamp_metadata(
        land_deed("Ramesh Kumar", "142/2A", "14-03-2019"),
        producer="Kaveri Online Services", creator="Sub-Registrar e-Records",
        created=issued_2019))

    # --- Fraud bundle: Suresh Patel.
    # Salary slip claims 80k (statement shows 40k), employer CIN is struck
    # off, and the amount was overwritten in a different font.
    (fraud / "salary_slip.pdf").write_bytes(_stamp_metadata(
        salary_slip("Suresh Patel", "AAAPS9999K", "U74999MH2012PTC234567",
                    "80,000.00", tampered_amount_font=True),
        producer="Adobe Photoshop 25.0 for Windows", creator="Adobe Photoshop",
        created=two_days_ago))
    (fraud / "bank_statement.pdf").write_bytes(_stamp_metadata(
        bank_statement("Suresh Patel", "AAAPS9999K", "40,000.00"),
        producer="Canara Bank e-Statement Service", creator="Canara Bank",
        created=last_month))
    # Deed claims a 2019 registration on someone else's survey number, but
    # the file itself was made two days ago in Photoshop.
    (fraud / "land_deed.pdf").write_bytes(_stamp_metadata(
        land_deed("Suresh Patel", "142/2A", "14-03-2019"),
        producer="Adobe Photoshop 25.0 for Windows", creator="Adobe Photoshop",
        created=two_days_ago))
    (fraud / "deed_photo.jpg").write_bytes(tampered_photo())

    for d in (clean, fraud):
        print(f"{d.name}/")
        for f in sorted(d.iterdir()):
            print(f"  {f.name}  ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
