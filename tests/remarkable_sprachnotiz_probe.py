#!/usr/bin/env python3
"""Probe des Sprachnotiz-Verknuepfers — die sicherheitskritische Logik.

Kein Kapitel ruft die echte claude-CLI oder fasst das echte Vault an: der
Modellaufruf wird mit einer Attrappe ersetzt, alles andere laeuft gegen
Wegwerf-Dateien. Geprueft werden vor allem die zwei Verteidigungen aus E-07:
Belegpflicht und Index-Begrenzung.

Aufruf
------
    tests/remarkable_sprachnotiz_probe.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(HIER))

import remarkable_sprachnotiz as rs

fehler_gesamt = 0


def pruefe(name: str, bedingung: bool, zusatz: str = "") -> None:
    global fehler_gesamt
    if bedingung:
        print(f"  OK    {name}")
    else:
        fehler_gesamt += 1
        print(f"  FEHLT {name} {zusatz}")


def kapitel_beleg() -> None:
    print("Kapitel 1 — Belegpflicht (das Programm rechnet nach)")
    quelle = "Ich habe hier noch Gedanken zum Skizze aufgenommen, siehe Skizze."
    pruefe("woertlicher Beleg wird akzeptiert",
           rs.beleg_gueltig("Gedanken zum Skizze", quelle))
    pruefe("Beleg mit anderem Whitespace wird akzeptiert",
           rs.beleg_gueltig("Gedanken   zum\nSkizze", quelle))
    pruefe("erfundener Beleg wird abgelehnt",
           not rs.beleg_gueltig("betrifft die Netzsegmentierung", quelle))
    pruefe("zu kurzer Beleg zaehlt nicht",
           not rs.beleg_gueltig("Skizze", quelle))
    pruefe("leerer Beleg zaehlt nicht", not rs.beleg_gueltig("", quelle))


def kapitel_modell() -> None:
    print("Kapitel 2 — Modellaufruf: Index-Begrenzung, JSON")
    kand = [{"pfad": "a.md", "dateiname": "a.md", "thema": "Skizze", "kontext": ""},
            {"pfad": "b.md", "dateiname": "b.md", "thema": "Netzplan", "kontext": ""}]
    orig = rs.modell_aufrufen
    try:
        rs.modell_aufrufen = lambda p, m, zeitgrenze=300, **kw: {
            "ok": True, "text": '{"index": 1, "beleg": "zum Netzplan gesprochen"}'}
        idx, beleg, _ = rs.frage_modell("Text zum Netzplan gesprochen", kand)
        pruefe("gueltiger Index wird uebernommen", idx == 1 and "Netzplan" in beleg)

        rs.modell_aufrufen = lambda p, m, zeitgrenze=300, **kw: {
            "ok": True, "text": '{"index": 99, "beleg": "x"}'}
        idx, _, _ = rs.frage_modell("t", kand)
        pruefe("Index ausserhalb des Bereichs -> Enthaltung (-1)", idx == -1)

        rs.modell_aufrufen = lambda p, m, zeitgrenze=300, **kw: {
            "ok": True, "text": '{"index": -1, "beleg": ""}'}
        idx, _, _ = rs.frage_modell("t", kand)
        pruefe("Modell-Enthaltung bleibt -1", idx == -1)

        rs.modell_aufrufen = lambda p, m, zeitgrenze=300, **kw: {"ok": True, "text": "kein json"}
        try:
            rs.frage_modell("t", kand)
            pruefe("Nicht-JSON-Antwort wirft", False)
        except RuntimeError:
            pruefe("Nicht-JSON-Antwort wirft", True)
    finally:
        rs.modell_aufrufen = orig


def kapitel_extraktion() -> None:
    print("Kapitel 3 — Kandidaten und Transkript aus dem Vault")
    with tempfile.TemporaryDirectory() as d:
        ordner = Path(d)
        (ordner / "zeichnung.md").write_text(
            "---\ntyp: artefakt-zeiger\n---\n# Skizze\n\n"
            "> [!quote] Kontext aus dem Mailrumpf\n> Skizze zur Zonenaufteilung.\n")
        (ordner / "sprach.md").write_text(
            "---\ntyp: sprachnotiz\nsource: transkript\n---\n# NOTIZ\n\n"
            "## Protokoll\n\nGedanken zum Skizze.\n\n## Herkunft\n\n"
            "der Transkript-Dienst-Link, soll NICHT im Transkript sein.\n")
        kand = rs.kandidaten(str(ordner))
        pruefe("Zeichnung als Kandidat erkannt",
               len(kand) == 1 and kand[0]["thema"] == "Skizze")
        pruefe("Kontext aus dem Zitatblock gezogen",
               "Zonenaufteilung" in kand[0]["kontext"])
        t = rs.transkript(str(ordner / "sprach.md"))
        pruefe("Transkript enthaelt den gesprochenen Text", "Skizze" in t)
        pruefe("Transkript ohne den Herkunft-Block", "der Transkript-Dienst-Link" not in t)


def kapitel_schreiben() -> None:
    print("Kapitel 4 — beidseitiger Wikilink, idempotent")
    with tempfile.TemporaryDirectory() as d:
        vault = Path(d)
        (vault / "CLAUDE.md").write_text("# t\n")
        ordner = vault / "02 Projekte" / "X" / "Notizen"
        ordner.mkdir(parents=True)
        sn = ordner / "2026-08-15 [X] NOTIZ Thema.md"
        zn = ordner / "2026-08-15 [X] Zeichnung.md"
        sn.write_text("---\ntyp: sprachnotiz\n---\n# NOTIZ\n\nText.\n")
        zn.write_text("---\ntyp: artefakt-zeiger\n---\n# Zeichnung\n")
        geaendert = rs.verknuepfe(str(sn), str(zn), str(vault))
        pruefe("beide Dateien geaendert", len(geaendert) == 2)
        pruefe("Sprachnotiz zeigt auf die Zeichnung",
               "[[2026-08-15 [X] Zeichnung]]" in sn.read_text())
        pruefe("Zeichnung zeigt zurueck auf die Sprachnotiz",
               "[[2026-08-15 [X] NOTIZ Thema]]" in zn.read_text())
        pruefe("Sprachnotiz gilt jetzt als verknuepft", rs.schon_verknuepft(str(sn)))
        # Zweiter Lauf: nichts doppelt.
        geaendert2 = rs.verknuepfe(str(sn), str(zn), str(vault))
        pruefe("zweiter Lauf haengt nichts doppelt an",
               geaendert2 == [] and sn.read_text().count("[[2026-08-15 [X] Zeichnung]]") == 1)
        # Beleg wird bei einer Modell-Entscheidung persistiert, idempotent.
        sn2 = ordner / "2026-08-15 [X] NOTIZ Zwei.md"
        sn2.write_text("---\ntyp: sprachnotiz\n---\n# NOTIZ\n\nText.\n")
        rs.verknuepfe(str(sn2), str(zn), str(vault), beleg="der belegende Satz")
        pruefe("Beleg in der Sprachnotiz persistiert",
               "> [!quote] Beleg (Modell-Entscheidung)" in sn2.read_text()
               and "der belegende Satz" in sn2.read_text())
        rs.verknuepfe(str(sn2), str(zn), str(vault), beleg="der belegende Satz")
        pruefe("Beleg nicht doppelt", sn2.read_text().count("Beleg (Modell-Entscheidung)") == 1)


def kapitel_digest() -> None:
    print("Kapitel 6 — HTML-Digest, Fremdtext escaped")
    zeile = {
        "kuerzel": "KOEINT",
        "sprach_thema": "Böser <script>alert(1)</script> Titel",
        "zeich_thema": "Zeichnung & Co",
        "beleg": "Zitat mit <b>HTML</b> & Sonderzeichen",
        "sharepoint": "https://sp/x.pdf", "transkript": "https://transkript/s",
        "obs_sn": "obsidian://open?vault=Vault&file=a",
        "obs_zn": "obsidian://open?vault=Vault&file=b",
    }
    out = rs.digest_html([zeile])
    pruefe("Fremdtext ist escaped (kein rohes <script>)", "<script>" not in out)
    pruefe("escaptes Zeichen ist da (&lt;script&gt;)", "&lt;script&gt;" in out)
    pruefe("Beleg escaped (&lt;b&gt;)", "&lt;b&gt;" in out)
    pruefe("SharePoint-Link im HTML", 'href="https://sp/x.pdf"' in out)
    pruefe("der Transkript-Dienst-Link im HTML", "https://transkript/s" in out)
    pruefe("obsidian-Link im HTML", "obsidian://open?vault=Vault&amp;file=a" in out
           or "obsidian://open?vault=Vault&file=a" in out)
    zwei = rs.digest_html([zeile, zeile])
    pruefe("Mehrzahl korrekt (2 Sprachnotizen)", "2 Sprachnotizen" in zwei)
    pruefe("Einzahl korrekt (1 Sprachnotiz)", "1 Sprachnotiz" in out and "Sprachnotizen" not in
           out.split("verknuepft")[0])


def kapitel_hash() -> None:
    print("Kapitel 5 — Kandidaten-Hash stabil, aenderungssensitiv")
    a = [{"dateiname": "a.md"}, {"dateiname": "b.md"}]
    b = [{"dateiname": "b.md"}, {"dateiname": "a.md"}]
    c = [{"dateiname": "a.md"}, {"dateiname": "c.md"}]
    pruefe("Reihenfolge egal (stabil)", rs.kandidaten_hash(a) == rs.kandidaten_hash(b))
    pruefe("andere Menge -> anderer Hash", rs.kandidaten_hash(a) != rs.kandidaten_hash(c))


def main() -> int:
    kapitel_beleg()
    kapitel_modell()
    kapitel_extraktion()
    kapitel_schreiben()
    kapitel_digest()
    kapitel_hash()
    if fehler_gesamt:
        print(f"\nROT — {fehler_gesamt} Pruefung(en) fehlgeschlagen.")
        return 1
    print("\nGRUEN — alle Pruefungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
