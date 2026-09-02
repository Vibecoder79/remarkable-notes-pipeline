#!/usr/bin/env python3
"""Wächter der reMarkable-Strecke: tote Links, liegengebliebene Dokumente, Stille.

Grundlage: E-01 «Auflagen», E-06 (nur Betrieb, nur Telegram).

Der Zeitstempel des letzten erfolgreichen Laufs von Abholer und Zuordner kommt
bereits aus dem Lebenszeichen-System (`heartbeat.sh` plus `jobs.tsv`) — den baut
dieser Wächter nicht nach. Er deckt die drei Signale ab, die kein Heartbeat sieht,
weil sie am INHALT hängen, nicht am Lauf:

  1. Tote `artefakt:`-Links — wird in SharePoint eine Datei verschoben oder
     gelöscht, zeigt der Link in der Vault-Notiz lautlos ins Leere.
  2. «Ohne Zuordnung», veraltet — ein Dokument ohne Kürzel bleibt liegen. Frisch
     ist das normal (der Zuordner löst es beim nächsten Lauf), aber ein Stapel,
     der Tage alt wird, wächst sonst unbemerkt.
  3. Stiller Eingang — kam lange nichts an, ist das Absicht oder ein Defekt. Der
     Wächter sagt es, statt Stille als Normalzustand zu behandeln.

Fehlerfälle (Anhang zu groß, Upload gescheitert) meldet der Abholer selbst über
seinen Rückgabewert an den Heartbeat — sie brauchen hier keine zweite Stelle.

Meldet NUR bei Befund (Stille = gesund, E-06 §2), höchstens einmal je Befund
(Merker gegen Alarm-Müdigkeit). Liest Vault und Bibliothek, schreibt nichts —
läuft deshalb ohne `mit-sperre.sh`.

Aufrufe:
    remarkable_wachhund.py
    remarkable_wachhund.py --dry     zeigen, was gemeldet würde
    remarkable_wachhund.py --alles   auch schon gemeldete Befunde zeigen
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from graph_basis import (DAUERHAFT, RC_DAUERHAFT, RC_OK, Fehler, geheimnis,
                                graph_mit_kopf, graph_token, melden)

BIBLIOTHEK = "remarkable"

# Ab wann ein «Ohne Zuordnung»-Dokument als liegengeblieben gilt. Der Zuordner
# löst zuordenbare binnen Minuten; was nach Tagen noch Status=Neu trägt, ist ein
# echter Nachzügler ohne gültiges Kürzel und braucht die Hand des Eigners.
OHNE_ZUORDNUNG_TAGE = float(os.environ.get("REMARKABLE_OHNE_TAGE", "3"))

# Ab wann Stille beim Eingang auffällt. Großzügig — der Eigner schickt nicht
# täglich. Nur geprüft, wenn es überhaupt Eingänge gab (leere Bibliothek am
# Anfang ist kein Defekt).
STILLE_TAGE = float(os.environ.get("REMARKABLE_STILLE_TAGE", "14"))

MERKER = Path(os.environ.get("REMARKABLE_WACHHUND_STATE",
                             "/var/lib/notizen-strecke/waechter-stand.json"))

ZEIGER_TYP = re.compile(r"^typ:\s*artefakt-zeiger\s*$", re.MULTILINE)
ARTEFAKT = re.compile(r"^artefakt:\s*(\S.*?)\s*$", re.MULTILINE)


def vault_wurzel():
    return os.environ.get("VAULT_DIR", "/opt/vault")


# --------------------------------------------------------------------------
# Reine Prüflogik — von der Probe ohne Netz und ohne Vault messbar
# --------------------------------------------------------------------------

def tote_links(zeiger: dict[str, str], bekannte_urls: set[str]) -> list[tuple[str, str]]:
    """Zeiger, deren `artefakt:`-URL nicht (mehr) in der Bibliothek steht.
    `zeiger` ist {url: notiz-pfad}. Gibt [(notiz, url), …]."""
    tot = []
    for url, notiz in sorted(zeiger.items(), key=lambda kv: kv[1]):
        if url and url != "unbekannt" and url not in bekannte_urls:
            tot.append((notiz, url))
    return tot


def _alter_tage(iso: str, jetzt: datetime) -> float | None:
    try:
        ts = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return (jetzt - ts).total_seconds() / 86400


def veraltete_ohne_zuordnung(eintraege: list[dict], jetzt: datetime,
                             tage: float = OHNE_ZUORDNUNG_TAGE) -> list[dict]:
    """Bibliothekseinträge mit Status=Neu, die älter als `tage` sind."""
    alt = []
    for e in eintraege:
        if (e.get("status") or "") != "Neu":
            continue
        a = _alter_tage(e.get("eingang") or "", jetzt)
        if a is not None and a >= tage:
            alt.append({**e, "alter_tage": round(a, 1)})
    return sorted(alt, key=lambda x: -x["alter_tage"])


def stiller_eingang(eintraege: list[dict], jetzt: datetime,
                    tage: float = STILLE_TAGE) -> float | None:
    """Alter des jüngsten Eingangs in Tagen, falls es die Schwelle übersteigt.
    None heißt: alles im Rahmen — oder es gab noch nie einen Eingang."""
    alter = [_alter_tage(e.get("eingang") or "", jetzt) for e in eintraege]
    alter = [a for a in alter if a is not None]
    if not alter:
        return None
    juengster = min(alter)
    return round(juengster, 1) if juengster >= tage else None


# --------------------------------------------------------------------------
# Erhebung aus Vault und Bibliothek
# --------------------------------------------------------------------------

def vault_zeiger(vault: str) -> dict[str, str]:
    """{artefakt-URL: vault-relativer Notizpfad} über alle `artefakt-zeiger`."""
    zeiger = {}
    for r, dirs, fs in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in fs:
            if not f.endswith(".md"):
                continue
            p = os.path.join(r, f)
            try:
                with open(p, encoding="utf-8") as fh:
                    kopf = fh.read(2048)
            except OSError:
                continue
            if not ZEIGER_TYP.search(kopf):
                continue
            m = ARTEFAKT.search(kopf)
            if m:
                zeiger[m.group(1).strip()] = os.path.relpath(p, vault)
    return zeiger


def bibliothek_eintraege(token: str) -> list[dict]:
    """Alle Einträge der Bibliothek mit Status, Eingang und Datei-URL."""
    site = geheimnis("m365.env", "M365_SITE_ID")
    r, _ = graph_mit_kopf(token, "GET", f"/sites/{site}/lists?$select=id,name")
    liste = next((l for l in r.get("value", [])
                  if (l.get("name") or "").lower() == BIBLIOTHEK), None)
    if not liste:
        raise Fehler(DAUERHAFT, f"Bibliothek '{BIBLIOTHEK}' nicht gefunden.")
    r, _ = graph_mit_kopf(
        token, "GET",
        f"/sites/{site}/lists/{liste['id']}/items?$expand=fields,driveItem&$top=500")
    eintraege = []
    for it in r.get("value", []):
        f = it.get("fields") or {}
        eintraege.append({
            "name": f.get("FileLeafRef") or (it.get("driveItem") or {}).get("name") or "",
            "status": f.get("Status") or "",
            "eingang": f.get("Eingang") or "",
            "url": (it.get("driveItem") or {}).get("webUrl") or it.get("webUrl") or "",
        })
    return eintraege


# --------------------------------------------------------------------------

def merker_lesen() -> set[str]:
    try:
        return set(json.loads(MERKER.read_text(encoding="utf-8")).get("gemeldet", []))
    except (OSError, json.JSONDecodeError):
        return set()


def merker_schreiben(keys: set[str]) -> None:
    neben = MERKER.with_suffix(".neu")
    neben.write_text(json.dumps({"gemeldet": sorted(keys),
                                 "stand": datetime.now().astimezone().isoformat()},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(neben, MERKER)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--alles", action="store_true")
    a = ap.parse_args()

    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 1

    try:
        token = graph_token()
        eintraege = bibliothek_eintraege(token)
    except Fehler as fehler:
        print(f"ABBRUCH ({fehler.klasse}): {fehler.text}", file=sys.stderr)
        return fehler.rc

    jetzt = datetime.now(timezone.utc)
    zeiger = vault_zeiger(vault)
    bekannte = {e["url"] for e in eintraege if e["url"]}

    tot = tote_links(zeiger, bekannte)
    alt = veraltete_ohne_zuordnung(eintraege, jetzt)
    still = stiller_eingang(eintraege, jetzt)
    ohne_gesamt = sum(1 for e in eintraege if e["status"] == "Neu")

    # Befund-Schlüssel für den Merker (gegen Wiederholung).
    keys = set()
    keys |= {f"totlink:{n}" for n, _ in tot}
    keys |= {f"ohne:{e['name']}" for e in alt}
    if still is not None:
        keys.add("stille")

    print(f"Bibliothek: {len(eintraege)} Einträge, davon {ohne_gesamt} ohne Zuordnung.")
    print(f"Vault-Zeiger: {len(zeiger)}. Tote Links: {len(tot)}. "
          f"Veraltet ohne Zuordnung: {len(alt)}. Stiller Eingang: "
          f"{'ja, ' + str(still) + ' Tage' if still is not None else 'nein'}.")

    if not keys:
        return RC_OK

    zeilen = []
    if tot:
        zeilen.append(f"TOTE LINKS  {len(tot)} Zeiger-Notiz(en) zeigen ins Leere:")
        for n, _ in tot[:5]:
            zeilen.append(f"  {n}")
        if len(tot) > 5:
            zeilen.append(f"  … und {len(tot) - 5} weitere")
        zeilen.append("  Datei in SharePoint verschoben/gelöscht? Link in der Notiz prüfen.")
    if alt:
        aelt = alt[0]
        zeilen.append(f"OHNE ZUORDNUNG  {len(alt)} Dokument(e) liegen ≥{int(OHNE_ZUORDNUNG_TAGE)} Tage:")
        zeilen.append(f"  ältestes: {aelt['name']} ({aelt['alter_tage']} Tage)")
        zeilen.append("  In SharePoint umbenennen (Kürzel in den Namen) — der nächste Lauf holt die Notiz nach.")
    if still is not None:
        zeilen.append(f"STILLER EINGANG  seit {still} Tagen kam nichts an.")
        zeilen.append("  Absicht — oder klemmt der Abholer? Lebenszeichen 'remarkable' prüfen.")
    text = "\n".join(zeilen)

    for zeile in zeilen:
        print(zeile)

    reported = set() if a.alles else merker_lesen()
    neu = keys - reported
    if not neu:
        if not a.dry:
            merker_schreiben(keys)   # auf aktive Befunde stutzen
        print("(nichts Neues — bereits gemeldet)")
        return RC_OK

    if a.dry:
        print("\n--- gemeldet würde ---")
        print(text)
        return RC_OK

    if melden(text):
        merker_schreiben(keys)
    else:
        print("WARNUNG: Meldung nicht zugestellt, Befund bleibt offen.", file=sys.stderr)
    return RC_DAUERHAFT


if __name__ == "__main__":
    sys.exit(main())
