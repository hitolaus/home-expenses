"""Regenerate sample_statement.pdf: an anonymized Danske Bank-style transaction list.

Run: python tests/fixtures/make_fixture.py   (needs reportlab, see requirements-dev.txt)
"""

from decimal import Decimal
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

HERE = Path(__file__).parent

# (date, description lines, amount) oldest first; balances are computed.
ROWS = [
    ("02.01.2026", ["Lønoverførsel"], "25000.00"),
    ("03.01.2026", ["NETTO NØRREBRO 12345"], "-312.50"),
    ("03.01.2026", ["Caffeine 63613"], "-45.00"),
    ("03.01.2026", ["Caffeine 63613"], "-45.00"),
    ("05.01.2026", ["JOE THE JUICE A/S\\", "\\Kobenhavn\\"], "-1234.56"),
    ("06.01.2026", ["Realkredit Danmark"], "-12062.98"),
    ("07.01.2026", ["Magasin refusion"], "199.95"),
] + [("%02d.01.2026" % (8 + i // 3), ["Rejsekort"], "-22.00") for i in range(60)]

OPENING = Decimal("1000.00")


def expected():
    """[(date, description lines, amount, balance)] newest first, as in the bank's export."""
    out, bal = [], OPENING
    for d, lines, amt in ROWS:
        bal += Decimal(amt)
        out.append((d, lines, Decimal(amt), bal))
    return out[::-1]


def dk(d: Decimal) -> str:
    s = f"{abs(d):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if d < 0 else "") + s


def write_pdf(path: Path, rows) -> None:
    """rows: [(date, description lines, amount, balance)] in the order they appear."""
    data = [["Dato", "Tekst", "Beløb", "Saldo", "Status", "Afstemt"]]
    data += [[d, "\n".join(lines), dk(a), dk(b), "Udført", "Nej"] for d, lines, a, b in rows]
    table = Table(data)
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, "grey"), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
    SimpleDocTemplate(str(path), pagesize=A4).build([table])


def main():
    write_pdf(HERE / "1234567890_2026.01.01-2026.01.31.pdf", expected())


if __name__ == "__main__":
    main()
