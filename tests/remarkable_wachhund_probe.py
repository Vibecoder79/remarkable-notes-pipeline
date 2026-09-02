#!/usr/bin/env python3
"""Probe des reMarkable-Wächters — die drei Prüflogiken.

Kein Kapitel fasst Netz oder Vault an: geprüft werden die reinen Funktionen
(tote_links, veraltete_ohne_zuordnung, stiller_eingang) gegen synthetische Daten.
Den Erhebungs- und Meldepfad fährt --dry gegen die echten Quellen von Hand.

Aufruf
------
    tests/remarkable_wachhund_probe.py
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(HIER))

import remarkable_wachhund as rw

fehler_gesamt = 0
JETZT = datetime(2026, 8, 15, 12, 0, tzinfo=timezone.utc)


def pruefe(name: str, bedingung: bool, zusatz: str = "") -> None:
    global fehler_gesamt
    if bedingung:
        print(f"  OK    {name}")
    else:
        fehler_gesamt += 1
        print(f"  FEHLT {name} {zusatz}")


def vor(tage: float) -> str:
    return (JETZT - timedelta(days=tage)).isoformat()


def kapitel_tote_links() -> None:
    print("Kapitel 1 — tote Links")
    zeiger = {
        "https://sp/a.pdf": "02 Projekte/X/Notizen/a.md",
        "https://sp/weg.pdf": "02 Projekte/X/Notizen/weg.md",
        "unbekannt": "02 Projekte/X/Notizen/ohne.md",
    }
    bekannte = {"https://sp/a.pdf", "https://sp/c.pdf"}
    tot = rw.tote_links(zeiger, bekannte)
    pruefe("verschwundene Datei wird als tot erkannt",
           tot == [("02 Projekte/X/Notizen/weg.md", "https://sp/weg.pdf")], f"({tot})")
    pruefe("vorhandene Datei ist nicht tot",
           all(u != "https://sp/a.pdf" for _, u in tot))
    pruefe("'unbekannt' zählt nicht als toter Link",
           all("ohne.md" not in n for n, _ in tot))


def kapitel_ohne_zuordnung() -> None:
    print("Kapitel 2 — veraltet ohne Zuordnung")
    eintraege = [
        {"name": "frisch.pdf", "status": "Neu", "eingang": vor(0.5)},
        {"name": "alt.pdf", "status": "Neu", "eingang": vor(5)},
        {"name": "erledigt.pdf", "status": "Verarbeitet", "eingang": vor(10)},
    ]
    alt = rw.veraltete_ohne_zuordnung(eintraege, JETZT, tage=3)
    pruefe("frisch Neu (0.5 Tage) zählt nicht", all(e["name"] != "frisch.pdf" for e in alt))
    pruefe("alt Neu (5 Tage) wird gemeldet", any(e["name"] == "alt.pdf" for e in alt))
    pruefe("Verarbeitet zählt nie", all(e["name"] != "erledigt.pdf" for e in alt))


def kapitel_stille() -> None:
    print("Kapitel 3 — stiller Eingang")
    frisch = [{"eingang": vor(2)}, {"eingang": vor(20)}]
    pruefe("jüngster Eingang vor 2 Tagen ist kein Befund",
           rw.stiller_eingang(frisch, JETZT, tage=14) is None)
    alt = [{"eingang": vor(20)}, {"eingang": vor(30)}]
    s = rw.stiller_eingang(alt, JETZT, tage=14)
    pruefe("jüngster Eingang vor 20 Tagen ist ein Befund", s is not None and s >= 20, f"({s})")
    pruefe("leere Bibliothek ist kein Befund",
           rw.stiller_eingang([], JETZT, tage=14) is None)


def main() -> int:
    kapitel_tote_links()
    kapitel_ohne_zuordnung()
    kapitel_stille()
    if fehler_gesamt:
        print(f"\nROT — {fehler_gesamt} Prüfung(en) fehlgeschlagen.")
        return 1
    print("\nGRÜN — alle Prüfungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
