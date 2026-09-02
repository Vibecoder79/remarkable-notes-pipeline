#!/usr/bin/env python3
"""Probe des reMarkable-Zuordners — Namens-/Rumpf-Logik, Notiz-Aufbau
und die PDF-Textebene (echtes pdftotext gegen ein handgebautes Mini-PDF).

Kein Kapitel fasst SharePoint oder das echte Vault an: geprueft werden die reinen
Funktionen gegen ein Wegwerf-Register. Der Netz-Pfad laeuft ueber `--pruefe-zugang`
und den Handlauf gegen eine Testdatei in der Bibliothek.

Aufruf
------
    tests/remarkable_zuordner_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(HIER))

import remarkable_zuordner as rz

fehler_gesamt = 0


def pruefe(name: str, bedingung: bool, zusatz: str = "") -> None:
    global fehler_gesamt
    if bedingung:
        print(f"  OK    {name}")
    else:
        fehler_gesamt += 1
        print(f"  FEHLT {name} {zusatz}")


# Wegwerf-Register: drei Baeume, ein Praefix-Paar fuer den Mehrdeutigkeitsfall.
REGISTER = {
    "ACME": "02 Projekte/ACME - Beispiel AG",
    "VTR-ACME": "09 Vertrieb/2026/EMS-Chemie — Projekt CIO",
    "P-MUSTER-M": "10 Personen/Muster Martina",
    "SBP": "02 Projekte/Notizen-Strecke",
    "SBP-INFRA": "02 Projekte/Notizen-Strecke/Infra",
}


def kapitel_name() -> None:
    print("Kapitel 1 — Kuerzel aus dem Dateinamen")

    titel = rz.name_zu_titel("2026-08-15 [ACME] Skizze.pdf")
    pruefe("Datum und Endung weg", titel == "[ACME] Skizze", f"({titel!r})")

    ziel, k, grund = rz.aufloesen("2026-08-15 [ACME] Skizze.pdf", "", REGISTER)
    pruefe("Projekt-Kuerzel loest auf",
           ziel == "02 Projekte/ACME - Beispiel AG" and k == "ACME", f"({grund})")

    ziel, k, _ = rz.aufloesen("2026-08-15 [VTR-ACME] Angebot.pdf", "", REGISTER)
    pruefe("Vertriebs-Kuerzel loest auf", ziel and k == "VTR-ACME")

    ziel, k, _ = rz.aufloesen("2026-08-15 [P-MUSTER-M] Skizze.pdf", "", REGISTER)
    pruefe("Personen-Kuerzel loest auf", ziel and k == "P-MUSTER-M")

    ziel, _, grund = rz.aufloesen("2026-08-15 [ZZZZ] Unbekannt.pdf", "", REGISTER)
    pruefe("unbekanntes Kuerzel bleibt ohne Zuordnung", ziel is None, f"({grund})")

    ziel, _, grund = rz.aufloesen("2026-08-15 Ohne Kuerzel.pdf", "", REGISTER)
    pruefe("kein Kuerzel im Namen, kein Rumpf -> ohne", ziel is None, f"({grund})")


def kapitel_rumpf() -> None:
    print("Kapitel 2 — Rueckfalllinie Mailrumpf")

    ziel, k, grund = rz.aufloesen("2026-08-15 Skizze ohne Kuerzel.pdf",
                                  "Gehoert zu [ACME], siehe Zonenplan.", REGISTER)
    pruefe("Rumpf-Kuerzel greift, wenn der Name keins hat",
           ziel == "02 Projekte/ACME - Beispiel AG" and k == "ACME", f"({grund})")

    ziel, k, grund = rz.aufloesen("2026-08-15 [ACME] Skizze.pdf",
                                  "eigentlich [VTR-ACME]", REGISTER)
    pruefe("Name gewinnt vor Rumpf", k == "ACME", f"({grund})")

    ziel, _, grund = rz.aufloesen("2026-08-15 Skizze.pdf",
                                  "betrifft [ACME] und [VTR-ACME]", REGISTER)
    pruefe("zwei Kuerzel im Rumpf sind mehrdeutig -> ohne", ziel is None, f"({grund})")

    ziel, _, _ = rz.aufloesen("2026-08-15 Skizze.pdf",
                              "nur [UNBEKANNT] steht hier", REGISTER)
    pruefe("unbekanntes Token im Rumpf zaehlt nicht", ziel is None)


def kapitel_notiz() -> None:
    print("Kapitel 3 — Notiz-Aufbau")

    md = rz.baue_notiz("Skizze", "ACME", "Skizze zur Zonenaufteilung.",
                       "https://contoso.sharepoint.com/.../Skizze.pdf",
                       "2026-08-15T09:30:00Z")
    pruefe("typ: artefakt-zeiger gesetzt", "typ: artefakt-zeiger" in md)
    pruefe("project: traegt das Kuerzel", "project: ACME" in md)
    pruefe("layer: roh gesetzt", "layer: roh" in md)
    pruefe("artefakt: ist die externe URL, kein Wikilink",
           "artefakt: https://contoso.sharepoint.com" in md and "original:" not in md)
    pruefe("ingested-external gesetzt", "origin: ingested-external" in md)
    pruefe("Kontext als Zitat gerahmt (Material, nie Auftrag)",
           "> [!quote] Kontext aus dem Mailrumpf" in md
           and "> Skizze zur Zonenaufteilung." in md)
    pruefe("H1 traegt das Thema", "# Skizze" in md)

    leer = rz.baue_notiz("Nur Skizze", "ACME", "", "https://x/y.pdf", "2026-08-15")
    pruefe("leerer Kontext erzeugt keinen Zitatblock", "[!quote]" not in leer)


def mini_pdf(text: str | None = None) -> bytes:
    """Ein minimales Ein-Seiten-PDF, handgebaut mit korrekter xref-Tabelle.
    Mit `text` traegt es eine echte Textebene; ohne ist die Seite leer — wie
    ein reMarkable-Export aus reiner Handschrift (Vektorzeichnung)."""
    if text is not None:
        inhalt = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("latin-1")
        objekte = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n%s\nendstream" % (len(inhalt), inhalt),
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
    else:
        objekte = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
        ]
    kopf = b"%PDF-1.4\n"
    teile, stellen = [kopf], []
    lauf = len(kopf)
    for nr, obj in enumerate(objekte, start=1):
        stueck = b"%d 0 obj\n%s\nendobj\n" % (nr, obj)
        stellen.append(lauf)
        teile.append(stueck)
        lauf += len(stueck)
    xref = [b"xref\n0 %d\n0000000000 65535 f \n" % (len(objekte) + 1)]
    xref += [b"%010d 00000 n \n" % s for s in stellen]
    teile.append(b"".join(xref))
    teile.append(b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
                 % (len(objekte) + 1, lauf))
    return b"".join(teile)


def kapitel_textebene() -> None:
    print("Kapitel 4 — Textebene aus dem PDF")

    text, gesamt = rz.pdf_textebene(mini_pdf("Diktierter Kommentar zur Skizze"))
    pruefe("Textebene wird extrahiert (echtes pdftotext auf dem Host)",
           text == "Diktierter Kommentar zur Skizze" and gesamt == len(text or ""),
           f"({text!r})")

    text, gesamt = rz.pdf_textebene(mini_pdf())
    pruefe("leere Seite (reine Handschrift) -> keine Textebene",
           text is None and gesamt == 0)

    text, gesamt = rz.pdf_textebene(b"das ist kein PDF")
    pruefe("kaputte Datei -> keine Textebene, kein Absturz", text is None)

    text, gesamt = rz.saeubere_text("Seite 1\f\fSeite 2\x00\x07\nZeile  \n\n\n\nEnde")
    pruefe("Saeuberung: Seitentrenner und Steuerzeichen raus, Leerzeilen zusammen",
           text == "Seite 1\n\nSeite 2\nZeile\n\nEnde", f"({text!r})")

    lang = "x" * (rz.TEXT_GRENZE + 500)
    text, gesamt = rz.saeubere_text(lang)
    pruefe("Kappung auf TEXT_GRENZE, Gesamtzahl bleibt ehrlich",
           len(text or "") == rz.TEXT_GRENZE and gesamt == len(lang))

    ebene = "Getippte Zeile\n\nZweite Zeile"
    md = rz.baue_notiz("Skizze", "ACME", "Rumpf.", "https://x/y.pdf",
                       "2026-08-15", ebene, len(ebene))
    pruefe("Abschnitt «Text aus dem Dokument» vorhanden",
           "## Text aus dem Dokument" in md)
    pruefe("Textebene als Zitat gerahmt, jede Zeile — auch die leere",
           "> [!quote] Textebene des PDFs" in md
           and "> Getippte Zeile" in md and "\n>\n> Zweite Zeile" in md)
    pruefe("ehrliche Grenze steht in der Notiz (kein OCR)", "kein OCR" in md)
    pruefe("ungekappt -> kein Gekappt-Hinweis", "Gekappt:" not in md)

    md = rz.baue_notiz("Z", "ACME", "", "https://x/y.pdf", "2026-08-15",
                       "kurz", 9999)
    pruefe("gekappt -> Hinweis mit beiden Zahlen",
           "Gekappt: 9999 Zeichen" in md and "die ersten 4" in md)

    md = rz.baue_notiz("Z", "ACME", "Rumpf.", "https://x/y.pdf", "2026-08-15")
    pruefe("ohne Textebene kein Abschnitt", "## Text aus dem Dokument" not in md)


def main() -> int:
    kapitel_name()
    kapitel_rumpf()
    kapitel_notiz()
    kapitel_textebene()
    if fehler_gesamt:
        print(f"\nROT — {fehler_gesamt} Pruefung(en) fehlgeschlagen.")
        return 1
    print("\nGRUEN — alle Pruefungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
