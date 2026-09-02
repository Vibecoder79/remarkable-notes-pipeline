#!/usr/bin/env python3
"""Probe des Kuerzel-Index — Gruppierung, PDF-Erzeugung, Fehlerklassen.

Der Kernpfad des Jobs ist Register -> drei Gruppen -> PDF -> Upload. Die ersten
drei Schritte laufen hier vollstaendig und echt (fpdf2 rendert, pdftotext liest
zurueck) — gegen ein Wegwerf-Vault, nie gegen den echten Bestand. Der Upload ist
Graph und laeuft ueber `--schreibprobe` gegen die echte Bibliothek (Handlauf,
Pflicht vor dem Cron-Eintrag); hier wird seine Fehlerklassen-Weiche geprueft:
fehlende Bibliothek muss VORUEBERGEHEND sein, nicht DAUERHAFT — sie entsteht
von Hand, der Job soll sich vertagen, nicht melden.

Aufruf
------
    tests/remarkable_index_probe.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(HIER))

import remarkable_index as ri
from graph_basis import VORUEBERGEHEND, Fehler

fehler_gesamt = 0


def pruefe(name: str, bedingung: bool, zusatz: str = "") -> None:
    global fehler_gesamt
    if bedingung:
        print(f"  OK    {name}")
    else:
        fehler_gesamt += 1
        print(f"  FEHLT {name} {zusatz}")


# Wegwerf-Register mit den Eigenheiten des echten: Umlaute im Ordnernamen,
# Verschachtelung (Kunden-Ordner, Jahrgang), ein sehr langer Name fuer den
# Zeilenumbruch, alle Baeume — seit E-08 auch Persoenliche Notizen (PN-),
# seit E-08 auch Bereiche.
REGISTER = {
    "SBP": "02 Projekte/Notizen-Strecke",
    "BKO": "02 Projekte/BEISPIEL-Mandate/2026-06-01 BKO - Assisstent - Körting",
    "LANG": ("02 Projekte/BEISPIEL-Mandate/Energy Infrastructure Partners/"
             "2026-06-29 AI Risk Management Integration und noch mehr Text"),
    "VTR-ACME": "09 Vertrieb/2026/EMS-Chemie — Projekt CIO",
    "P-MUSTER-M": "10 Personen/Muster Martina",
    "P-MUELLER-K": "10 Personen/Müller Katharina",
    "PN-LEARN": "04 Ressourcen/Persönliche Notizen/Lifelong Learning",
    "BEREICH-A": "03 Bereiche/ein Bereich",
    "INSO": "03 Bereiche/der Eigner privat/Privatinsolvenz",
}


def kapitel_gruppierung() -> None:
    print("Kapitel 1 — Gruppierung in die Baeume")

    gruppen = ri.gruppieren(REGISTER)
    namen = [n for n, _ in gruppen]
    # Fuenf seit E-08. Die Zahl steht hier absichtlich hart: kaeme ein Baum
    # ins Register und nicht in BAEUME, fiele er in die Auffanggruppe
    # «Ausserhalb der Bäume» — und diese Pruefung soll das melden, nicht dulden.
    pruefe("fuenf Gruppen in fester Reihenfolge",
           namen == ["Projekte", "Vertrieb", "Personen", "Persönliche Notizen",
                     "Bereiche"],
           f"({namen})")
    pruefe("kein Kuerzel faellt in die Auffanggruppe",
           "Ausserhalb der Bäume" not in namen, f"({namen})")

    inhalt = dict(gruppen)
    pruefe("Projekte: 3 Eintraege", len(inhalt["Projekte"]) == 3)
    pruefe("Vertrieb: 1 Eintrag", len(inhalt["Vertrieb"]) == 1)
    pruefe("Personen: 2 Eintraege", len(inhalt["Personen"]) == 2)
    themen = dict(inhalt["Persönliche Notizen"])
    pruefe("Persoenliche Notizen: PN-Kuerzel mit Kategorie-Ordner",
           themen.get("PN-LEARN") == "Lifelong Learning", f"({themen})")
    bereiche = dict(inhalt["Bereiche"])
    pruefe("Bereiche: Hub direkt unter der Wurzel (E-08)",
           bereiche.get("BEREICH-A") == "ein Bereich", f"({bereiche})")
    pruefe("Bereiche: verschachtelter Hub behaelt die Zwischenebene",
           bereiche.get("INSO") == "der Eigner privat/Privatinsolvenz",
           f"({bereiche})")

    kuerzel = [k for k, _ in inhalt["Projekte"]]
    pruefe("je Gruppe alphabetisch nach Kuerzel",
           kuerzel == sorted(kuerzel), f"({kuerzel})")

    ordner = dict(inhalt["Vertrieb"])["VTR-ACME"]
    pruefe("Ordnername relativ zur Baum-Wurzel, Zwischenebene bleibt",
           ordner == "2026/EMS-Chemie — Projekt CIO", f"({ordner!r})")

    fremd = ri.gruppieren({"XX": "06 Archiv/Irgendwas"})
    pruefe("unbekannter Baum wird gezeigt, nicht verschluckt",
           any(n.startswith("Ausserhalb") and eintraege
               for n, eintraege in fremd))


def kapitel_pdf(tmp: Path) -> None:
    print("Kapitel 2 — PDF-Erzeugung (echtes fpdf2, echtes pdftotext)")

    pfad = tmp / "index.pdf"
    gesamt = ri.pdf_bauen(ri.gruppieren(REGISTER), pfad, stand="2026-08-16 00:00")
    pruefe("alle Kuerzel gezaehlt", gesamt == len(REGISTER), f"({gesamt})")
    roh = pfad.read_bytes()
    pruefe("Datei beginnt mit %PDF", roh.startswith(b"%PDF"))

    text = subprocess.run(["pdftotext", str(pfad), "-"],
                          capture_output=True, text=True).stdout
    pruefe("Namensregel Dokument steht oben", "[KUERZEL] Thema" in text)
    pruefe("Namensregel Sprachnotiz steht oben", "[KUERZEL] NOTIZ Thema" in text)
    pruefe("Gruppenkopf mit Zaehler", "Projekte (3)" in text)
    pruefe("Umlaut im Ordnernamen ueberlebt", "Körting" in text)
    pruefe("Umlaut im Personennamen ueberlebt", "Müller Katharina" in text)
    pruefe("Gedankenstrich ueberlebt", "EMS-Chemie — Projekt CIO" in text)
    pruefe("jedes Kuerzel im PDF",
           all(k in text for k in REGISTER), )


def kapitel_fehlerklassen() -> None:
    print("Kapitel 3 — Fehlerklassen")

    try:
        ri.bibliothek_aus_antwort({"value": [{"name": "remarkable"},
                                             {"name": "Freigaben"}]})
        pruefe("fehlende Bibliothek wirft", False)
    except Fehler as fehler:
        pruefe("fehlende Bibliothek ist VORUEBERGEHEND (vertagen)",
               fehler.klasse == VORUEBERGEHEND, f"({fehler.klasse})")

    kennung = ri.bibliothek_aus_antwort(
        {"value": [{"name": "an-remarkable", "id": "abc"}]})
    pruefe("vorhandene Bibliothek loest auf", kennung == "abc")

    # Der echte Fall vom 2026-08-16: SharePoint streicht beim Anlegen von Hand
    # den Bindestrich aus dem internen Namen — der Anzeigename muss reichen.
    kennung = ri.bibliothek_aus_antwort(
        {"value": [{"name": "anremarkable", "displayName": "an-remarkable",
                    "id": "xyz"}]})
    pruefe("Anzeigename loest auf, wenn der interne den Bindestrich verlor",
           kennung == "xyz")


def kapitel_lauf(tmp: Path) -> None:
    print("Kapitel 4 — der Job-Kernpfad gegen ein Wegwerf-Vault")

    vault = tmp / "vault"
    (vault / "02 Projekte" / "Probe Projekt").mkdir(parents=True)
    (vault / "10 Personen" / "Bär Test").mkdir(parents=True)
    (vault / "04 Ressourcen" / "Persönliche Notizen" / "Lernen Probe").mkdir(
        parents=True)
    (vault / "CLAUDE.md").write_text("# Probe", encoding="utf-8")
    (vault / "02 Projekte" / "Probe Projekt" / "Hub.md").write_text(
        "---\nmeeting_key: PRB\n---\n", encoding="utf-8")
    (vault / "10 Personen" / "Bär Test" / "Bär Test.md").write_text(
        "---\nmeeting_key: P-BAER-T\n---\n", encoding="utf-8")
    (vault / "04 Ressourcen" / "Persönliche Notizen" / "Lernen Probe" /
     "Lernen Probe.md").write_text(
        "---\nmeeting_key: PN-PRB\n---\n", encoding="utf-8")

    ziel = tmp / "lauf.pdf"
    umgebung = dict(os.environ, VAULT_DIR=str(vault))
    lauf = subprocess.run(
        [sys.executable, str(HIER / "remarkable_index.py"), "--ausgabe", str(ziel)],
        capture_output=True, text=True, env=umgebung)
    pruefe("Lauf endet mit rc=0", lauf.returncode == 0,
           f"(rc={lauf.returncode}, {lauf.stderr.strip()[:120]})")
    pruefe("PDF liegt da", ziel.is_file())
    if ziel.is_file():
        text = subprocess.run(["pdftotext", str(ziel), "-"],
                              capture_output=True, text=True).stdout
        pruefe("Kuerzel aus dem Wegwerf-Vault im PDF",
               "PRB" in text and "P-BAER-T" in text)
        pruefe("PN-Kuerzel aus dem vierten Baum im PDF (E-08)",
               "PN-PRB" in text and "Lernen Probe" in text)

    leer = tmp / "leer"
    (leer / "02 Projekte").mkdir(parents=True)
    (leer / "CLAUDE.md").write_text("# Probe", encoding="utf-8")
    lauf = subprocess.run(
        [sys.executable, str(HIER / "remarkable_index.py"),
         "--ausgabe", str(tmp / "nie.pdf")],
        capture_output=True, text=True, env=dict(os.environ, VAULT_DIR=str(leer)))
    pruefe("leeres Register laedt NICHT hoch, rc=dauerhaft",
           lauf.returncode == 77 and not (tmp / "nie.pdf").exists(),
           f"(rc={lauf.returncode})")


def main() -> int:
    print("Probe Kuerzel-Index\n")
    with tempfile.TemporaryDirectory() as tmp:
        kapitel_gruppierung()
        kapitel_pdf(Path(tmp))
        kapitel_fehlerklassen()
        kapitel_lauf(Path(tmp))
    print(f"\n{'BESTANDEN' if not fehler_gesamt else f'{fehler_gesamt} FEHLER'}")
    return 1 if fehler_gesamt else 0


if __name__ == "__main__":
    sys.exit(main())
