#!/usr/bin/env python3
"""Probe des reMarkable-Abholers — das Mail-Gate und die Namenslogik.

Warum es diese Datei gibt
-------------------------
Das DMARC-Gate ist der Eingang der ganzen Strecke: Der Rumpftext wird zum
Kontextsatz der Vault-Notiz, zum Inhalt der SharePoint-Spalte und ab dem Sprachnotiz-Zweig
zum Eingabetext eines Sprachmodells. Ein Gate, das stillschweigend durchlaesst,
faellt im Betrieb nicht auf — eine Mail von einem Angreifer sieht aus wie eine
vom Tablet. Deshalb misst die Probe jede Fehlerklasse des Gates einzeln, mit
echten Kopfzeilen-Formen, wie Exchange Online sie liefert.

Kein Kapitel beruehrt Tenant, Postfach oder Bibliothek: geprueft werden die
reinen Funktionen (dmarc_verdikt, rumpf_kappen, ziel_name, sichere_dateiname).
Den Netz-Pfad fahren `--pruefe-zugang` und die Gegenprobe mit gefaelschtem
Absender (von Hand je Anlass).

Aufruf
------
    tests/remarkable_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(HIER))

import remarkable_abholer as ra

fehler_gesamt = 0


def pruefe(name: str, bedingung: bool, zusatz: str = "") -> None:
    global fehler_gesamt
    if bedingung:
        print(f"  OK    {name}")
    else:
        fehler_gesamt += 1
        print(f"  FEHLT {name} {zusatz}")


def kopf(auth: str | None) -> list[dict]:
    zeilen = [{"name": "Subject", "value": "Dokument von meinem reMarkable"}]
    if auth is not None:
        zeilen.append({"name": "Authentication-Results", "value": auth})
    return zeilen


# Echte Form einer Exchange-Online-Kopfzeile, verkuerzt.
ECHT = ("spf=pass (sender IP is 8.29.226.4) smtp.mailfrom=share.remarkable.com; "
        "dkim=pass (signature was verified) header.d=remarkable.com; "
        "dmarc=pass action=none header.from=remarkable.com; compauth=pass reason=100")


def kapitel_gate() -> None:
    print("Kapitel 1 — das DMARC-Gate")

    ok, grund = ra.dmarc_verdikt(kopf(ECHT), "my@remarkable.com")
    pruefe("echte Tablet-Mail passiert", ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf(ECHT.replace("header.from=remarkable.com",
                                                   "header.from=share.remarkable.com")),
                                 "my=remarkable.com@share.remarkable.com")
    pruefe("share-Subdomain mit passendem Alignment passiert", ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf(ECHT), "boss@evil.example")
    pruefe("fremde Absender-Domain faellt", not ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf(None), "my@remarkable.com")
    pruefe("fehlende Authentication-Results faellt", not ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf(ECHT.replace("dmarc=pass", "dmarc=fail")),
                                 "my@remarkable.com")
    pruefe("dmarc=fail faellt", not ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf(ECHT.replace("dmarc=pass", "dmarc=none")),
                                 "my@remarkable.com")
    pruefe("dmarc=none faellt (kein Pass ist kein Pass)", not ok, f"({grund})")

    # Der Spoof-Fall, gegen den das Gate gebaut ist: From behauptet remarkable,
    # DMARC bestand aber fuer die Domain des Angreifers.
    ok, grund = ra.dmarc_verdikt(kopf("spf=pass smtp.mailfrom=evil.example; "
                                      "dmarc=pass action=none header.from=evil.example"),
                                 "my@share.remarkable.com")
    pruefe("dmarc=pass fuer fremde Domain faellt (Alignment)", not ok, f"({grund})")

    ok, grund = ra.dmarc_verdikt(kopf("dmarc=pass action=none"), "my@remarkable.com")
    pruefe("dmarc=pass ohne header.from faellt (Alignment unbelegt)", not ok, f"({grund})")


def kapitel_rumpf() -> None:
    print("Kapitel 2 — Rumpf kappen")

    text = "Skizze zur Zonenaufteilung, gehoert zu ACME.\r\n--\r\nVon meinem reMarkable Paper Tablet gesendet\r\nBitte nicht antworten"
    gekappt = ra.rumpf_kappen(text)
    pruefe("Trennlinie schneidet die Signatur weg",
           gekappt == "Skizze zur Zonenaufteilung, gehoert zu ACME.", f"({gekappt!r})")

    gekappt = ra.rumpf_kappen("Kontext ohne Trennlinie\nVon meinem reMarkable Tablet")
    pruefe("Herstellersatz als Rueckfalllinie", gekappt == "Kontext ohne Trennlinie",
           f"({gekappt!r})")

    gekappt = ra.rumpf_kappen("a" * 10000)
    pruefe("Laenge wird gekappt und markiert",
           len(gekappt) < 10000 and gekappt.endswith("…[gekappt]"), f"({len(gekappt)})")

    pruefe("leerer Rumpf bleibt leer", ra.rumpf_kappen(None) == "")


def kapitel_namen() -> None:
    print("Kapitel 3 — Zielnamen")

    name = ra.ziel_name("[ACME] Skizze.pdf", "2026-08-15T09:30:00Z")
    pruefe("Datum vorangestellt, Endung erhalten",
           name == "2026-08-15 [ACME] Skizze.pdf", f"({name!r})")

    name = ra.ziel_name("Skizze: Netz/Plan?.pdf", "2026-08-15T09:30:00Z")
    pruefe("verbotene Zeichen ersetzt", ":" not in name and "/" not in name and "?" not in name,
           f"({name!r})")

    name = ra.ziel_name("[ACME] Skizze.pdf", "2026-08-15T09:30:00Z", " 0930")
    pruefe("Uhrzeit-Zusatz vor der Endung",
           name == "2026-08-15 [ACME] Skizze 0930.pdf", f"({name!r})")

    pruefe("Punkte am Rand entfernt (SharePoint-Regel)",
           not ra.sichere_dateiname("..boese.").startswith(".")
           and not ra.sichere_dateiname("..boese.").endswith("."))


def main() -> int:
    kapitel_gate()
    kapitel_rumpf()
    kapitel_namen()
    if fehler_gesamt:
        print(f"\nROT — {fehler_gesamt} Pruefung(en) fehlgeschlagen.")
        return 1
    print("\nGRUEN — alle Pruefungen bestanden.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
