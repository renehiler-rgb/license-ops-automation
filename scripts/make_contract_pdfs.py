"""
make_contract_pdfs.py - turn data/contracts.json into realistic contract PDFs.

Run it from the project root (reportlab is in scripts/requirements.txt):
  .venv/bin/python scripts/make_contract_pdfs.py

It writes 7 files into sample-contracts/:
  - 6 contracts, one per entry in data/contracts.json, in three different layouts and wordings
    so the extraction in workflow C is not trivial (dates written in words, "ninety (90) days",
    the price only inside a table, and so on)
  - 1 invoice that is NOT a contract, to test the "needs review" path

Everything is synthetic: the company is Northwind Media and all values come from data/contracts.json.
The output is deterministic (no random numbers), so running it twice gives the same text.
"""

import json
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "sample-contracts"

BUYER = "Northwind Media d.o.o."
BUYER_ADDRESS = "Bulevar Oslobodjenja 10, 21000 Novi Sad, Serbia"

STYLES = getSampleStyleSheet()
BODY = ParagraphStyle("body", parent=STYLES["BodyText"], fontSize=10, leading=14, spaceAfter=6)
TITLE = ParagraphStyle("title", parent=STYLES["Title"], fontSize=18, spaceAfter=10)
HEADING = ParagraphStyle("heading", parent=STYLES["Heading2"], fontSize=12, spaceBefore=10, spaceAfter=4)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, textColor=colors.grey)

NUMBER_WORDS = {30: "thirty", 60: "sixty", 90: "ninety"}
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]


# ---------- small helpers that format the same value in different ways ----------

def iso(value: str) -> date:
    return date.fromisoformat(value)


def date_long(value: str) -> str:
    """2026-02-18 -> 18 February 2026"""
    d = iso(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def date_words(value: str) -> str:
    """2026-01-19 -> the 19th day of January, 2026"""
    d = iso(value)
    return f"the {ordinal(d.day)} day of {MONTHS[d.month - 1]}, {d.year}"


def notice_in_words(days: int) -> str:
    """90 -> ninety (90) days"""
    return f"{NUMBER_WORDS.get(days, str(days))} ({days}) days"


def money(amount: float) -> str:
    return f"USD {amount:,.2f}"


def table(rows: list[list[str]], widths: list[float]) -> Table:
    """A simple grid table with a grey header row."""
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def build_pdf(path: Path, story: list) -> None:
    # invariant=1 leaves out the creation time and random id, so the same input always gives the same bytes
    # (and the same sha256, which the intake workflow uses to detect duplicates).
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=18 * mm, bottomMargin=18 * mm, invariant=1)
    doc.build(story)


# ---------- the three contract layouts ----------

def layout_formal(c: dict, tool: dict) -> list:
    """Style A: numbered clauses, pricing in a table, dates like '18 February 2026'."""
    annual = c["seats"] * c["price_per_seat"] * 12
    cycle = "annually in advance" if c["billing_cycle"] == "annual" else "monthly in arrears"
    renew = (f"This Agreement renews automatically for successive periods of twelve (12) months unless either party "
             f"gives written notice of non-renewal at least {notice_in_words(c['notice_days'])} before the end of the "
             f"then-current term." if c["auto_renew"] else
             f"This Agreement does not renew automatically. To extend it, the parties must agree in writing at least "
             f"{notice_in_words(c['notice_days'])} before the end of the term.")
    return [
        Paragraph(f"SOFTWARE SUBSCRIPTION ORDER FORM", TITLE),
        Paragraph(f"Contract reference: <b>{c['contract_ref']}</b>", BODY),
        Paragraph("1. Parties", HEADING),
        Paragraph(f"This Order Form is made between <b>{tool['vendor']}</b> (the \"Supplier\") and <b>{BUYER}</b>, "
                  f"{BUYER_ADDRESS} (the \"Customer\"). The Customer's contract owner is {c['owner_email']}.", BODY),
        Paragraph("2. Subscription", HEADING),
        Paragraph(f"The Supplier grants the Customer a subscription to <b>{tool['name']}</b> for the seats listed below.", BODY),
        table([["Item", "Detail"],
               ["Product", tool["name"]],
               ["Licensed seats", str(c["seats"])],
               ["Price per seat per month", money(c["price_per_seat"])],
               ["Billing", f"Charged {cycle}"],
               ["Total annual fee", money(annual)]], [60 * mm, 100 * mm]),
        Paragraph("3. Term", HEADING),
        Paragraph(f"The term starts on {date_long(c['start_date'])} and ends on {date_long(c['end_date'])} "
                  f"(the \"Initial Term\").", BODY),
        Paragraph("4. Renewal and notice", HEADING),
        Paragraph(renew, BODY),
        PageBreak(),
        Paragraph("5. Termination", HEADING),
        Paragraph("Either party may terminate this Agreement for material breach that remains uncured thirty (30) days after "
                  "written notice. On termination the Customer's access ends and the Supplier will export the Customer's "
                  "data on request.", BODY),
        Paragraph("6. Service levels", HEADING),
        Paragraph("The Supplier will make the service available 99.5% of each calendar month, excluding planned maintenance. "
                  "If availability falls below 99.5% the Customer receives a service credit of 5% of that month's fees.", BODY),
        Paragraph("7. Data protection", HEADING),
        Paragraph("The Supplier processes personal data only on the Customer's documented instructions, applies appropriate "
                  "technical and organisational measures, and notifies the Customer of a personal data breach without undue "
                  "delay and in any event within 72 hours.", BODY),
        Paragraph("8. Governing law", HEADING),
        Paragraph("This Agreement is governed by the laws of the Republic of Serbia.", BODY),
        Spacer(1, 10),
        Paragraph(f"Signed for {tool['vendor']}: ____________________  Signed for {BUYER}: ____________________", SMALL),
    ]


def layout_prose(c: dict, tool: dict) -> list:
    """Style B: letter-like prose, price and notice period written in sentences."""
    cycle = ("The fees are invoiced once a year in advance" if c["billing_cycle"] == "annual"
             else "The fees are invoiced every month")
    renew = (f"If neither party objects, the agreement continues for another year. A party that does not want the "
             f"agreement to continue must tell the other in writing {c['notice_days']} days before the end date."
             if c["auto_renew"] else
             f"The agreement ends on the end date and does not continue by itself. If the Customer wants to keep "
             f"the service it must tell the Supplier {c['notice_days']} days before the end date.")
    return [
        Paragraph(f"{tool['name']} Licence Agreement", TITLE),
        Paragraph(f"Agreement no. {c['contract_ref']}", BODY),
        Paragraph("This agreement is between " f"{tool['vendor']} and {BUYER}. "
                  f"{BUYER} named {c['owner_email']} as the person responsible for this contract.", BODY),
        Paragraph("What you get", HEADING),
        Paragraph(f"{BUYER} may use {tool['name']} with up to {c['seats']} named users. "
                  f"Each seat costs {money(c['price_per_seat'])} per month. {cycle}. "
                  f"All prices are in US dollars and exclude VAT.", BODY),
        Paragraph("How long it lasts", HEADING),
        Paragraph(f"The agreement begins on {date_long(c['start_date'])} and runs until {date_long(c['end_date'])}. "
                  f"{renew}", BODY),
        Paragraph("Ending the agreement early", HEADING),
        Paragraph("Either side can end the agreement early if the other side seriously breaks it and does not fix the problem "
                  "within 30 days of being told. Unused prepaid fees are not refunded unless the Supplier is at fault.", BODY),
        PageBreak(),
        Paragraph("Service quality", HEADING),
        Paragraph("The service should be available 99.9% of the time each month. Support answers urgent problems within "
                  "four business hours.", BODY),
        Paragraph("Your data", HEADING),
        Paragraph("Customer data stays the property of the Customer. The Supplier stores it in the European Union, uses it only to "
                  "run the service, and deletes it within 60 days after the agreement ends.", BODY),
        Spacer(1, 10),
        Paragraph(f"Accepted by {BUYER} and {tool['vendor']}.", SMALL),
    ]


def layout_messy(c: dict, tool: dict) -> list:
    """Style C (deliberately messy): the price is only in a table, dates are written in words,
    the notice period is 'ninety (90) days' and the seat count sits in a table cell."""
    return [
        Paragraph(f"MASTER SERVICES AGREEMENT", TITLE),
        Paragraph(f"Ref. {c['contract_ref']} - Schedule 1 applies", SMALL),
        Paragraph("Preamble", HEADING),
        Paragraph(f"{tool['vendor']} (\"Provider\") and {BUYER} (\"Client\") agree as follows. The Provider's product "
                  f"<b>{tool['name']}</b> is supplied under Schedule 1. Contact for the Client: {c['owner_email']}.", BODY),
        Paragraph("Term", HEADING),
        Paragraph(f"This agreement takes effect on {date_words(c['start_date'])} and, unless ended earlier under this "
                  f"agreement, expires on {date_words(c['end_date'])}.", BODY),
        Paragraph("Renewal", HEADING),
        Paragraph((f"The agreement is renewed automatically for further twelve-month terms. Either party may prevent "
                   f"renewal by written notice given not later than {notice_in_words(c['notice_days'])} prior to expiry."
                   if c["auto_renew"] else
                   f"There is no automatic renewal. A request to extend must be made not later than "
                   f"{notice_in_words(c['notice_days'])} prior to expiry."), BODY),
        Paragraph("Fees", HEADING),
        Paragraph("Fees are set out in Schedule 1 and are payable "
                  + ("yearly in advance." if c["billing_cycle"] == "annual" else "monthly.")
                  + " Amounts are in US dollars.", BODY),
        PageBreak(),
        Paragraph("Schedule 1 - Order", HEADING),
        table([["Service", "Qty", "Unit", "Rate"],
               [tool["name"], str(c["seats"]), "seat / month", f"{c['price_per_seat']:.2f}"]],
              [60 * mm, 20 * mm, 40 * mm, 30 * mm]),
        Spacer(1, 8),
        Paragraph("Termination, service levels and data", HEADING),
        Paragraph("Either party may terminate if the other commits a material breach that stays uncured for thirty (30) "
                  "consecutive days. The Provider targets 99.5% monthly availability. Personal data is processed under the data "
                  "processing addendum attached to this agreement and is deleted on termination.", BODY),
    ]


# Which layout each contract gets. The messy one goes to NW-MTS-001, whose notice period is ninety days.
LAYOUT_FOR = {
    "NW-CHT-001": layout_formal,
    "NW-DSH-001": layout_prose,
    "NW-CFG-001": layout_formal,
    "NW-MTS-001": layout_messy,
    "NW-DSH-002": layout_prose,
    "NW-CFG-002": layout_prose,
}


# ---------- the document that is NOT a contract ----------

def make_invoice(path: Path, tool: dict) -> None:
    story = [
        Paragraph("INVOICE", TITLE),
        Paragraph(f"Invoice no. INV-2026-0412 &nbsp;&nbsp; Date: 30 September 2026", BODY),
        Paragraph(f"From: {tool['vendor']}<br/>To: {BUYER}, {BUYER_ADDRESS}", BODY),
        Spacer(1, 8),
        table([["Description", "Qty", "Unit price", "Amount"],
               [f"{tool['name']} seats, September 2026", "147", "18.00", "2,646.00"],
               ["Premium support", "1", "250.00", "250.00"],
               ["", "", "Total due", "USD 2,896.00"]], [80 * mm, 20 * mm, 30 * mm, 30 * mm]),
        Spacer(1, 8),
        Paragraph("Payment due within 14 days. Bank transfer to the account on file.", BODY),
    ]
    build_pdf(path, story)


def main() -> None:
    contracts = json.loads((DATA / "contracts.json").read_text(encoding="utf-8"))
    tools = {t["slug"]: t for t in json.loads((DATA / "tools.json").read_text(encoding="utf-8"))}
    OUT.mkdir(exist_ok=True)

    for contract in contracts:
        tool = tools[contract["tool"]]
        layout = LAYOUT_FOR.get(contract["contract_ref"], layout_formal)
        name = f"{contract['contract_ref']}_{tool['name'].replace(' ', '-')}.pdf"
        build_pdf(OUT / name, layout(contract, tool))
        print(f"wrote {name}  ({layout.__name__})")

    make_invoice(OUT / "INV-2026-0412_DesignHub-invoice.pdf", tools["designhub"])
    print("wrote INV-2026-0412_DesignHub-invoice.pdf  (not a contract)")


if __name__ == "__main__":
    main()
