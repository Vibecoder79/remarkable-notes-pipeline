#!/usr/bin/env python3
"""Ordnet eine Sitzung des Transkript-Dienstes einem Projekt zu. Deterministisch, ohne Sprachmodell.

Grundlage: E-08 Transkript-Anbindung. Die API des Transkript-Dienstes liefert **keine Teilnehmer, keine
Sprachangabe, keine freien Tags und keinen Kalenderbezug** — das wurde am 2026-07-29
gegen die vollstaendige OpenAPI-Spec geprueft, null Treffer fuer `participant`,
`attendee`, `language`, `calendar`. Eine Zuordnung ueber Teilnehmer-Domains, der
naheliegende Weg, ist damit unmoeglich.

Bleibt das Kuerzel im Titel: `[KUERZEL] Thema`. Das ist Zeichenvergleich, kein
Verstehen — und gehoert deshalb in ein Programm, nicht in ein Sprachmodell. Ein Modell
wuerde hier raten, wo es nichts zu raten gibt.

Aufruf:
    kuerzel_register.py --titel "[PROJ] Lebenszeichen bauen"
    kuerzel_register.py --selbsttest
"""
import argparse
import os
import re
import sys

KUERZEL_MUSTER = re.compile(r'^\s*\[([A-Z0-9-]{2,})\]\s*(.*)$')
# Ein Kuerzel ist ein Kuerzel — egal ob es an einem Projekt-Hub (`meeting_key`) oder
# an einem Lead in `09 Vertrieb` (`lead_key`) haengt. Beide landen im selben Register,
# damit die Kollisionspruefung baum-uebergreifend greift.
FRONTMATTER_KEY = re.compile(
    r'^(?:meeting_key|lead_key):\s*["\']?([A-Z0-9-]+)["\']?\s*$', re.MULTILINE)

# Baeume, aus denen das Register gebaut wird. Reihenfolge ist ohne Bedeutung.
# "10 Personen" seit 2026-08-10 (E-08): Eins-zu-eins-Meetings tragen ein
# P-Kuerzel und landen im Ordner der Person.
# Seit 2026-08-13 (E-08) tragen auch flache Kontakt-Notizen in
# `09 Vertrieb/_Kontakte/` ein P-Kuerzel — schon bei der Anlage. Fuer sie zeigt
# das Register nicht auf ihren Ablageort, sondern auf den KUENFTIGEN
# Personen-Ordner `10 Personen/<Name>`; der Abholer materialisiert ihn beim
# ersten Meeting und zieht die Notiz als Hub um.
# "04 Ressourcen/Persönliche Notizen" seit 2026-08-16 (E-08): der vierte
# Baum fuer Themen ohne Projekt-, Personen- oder Lead-Charakter (Lifelong
# Learning, allgemeine Notizen). Kategorien sind Ordner mit Hub-Notiz, deren
# meeting_key das Praefix `PN-` traegt. Bewusst NUR dieser Unterordner, nicht
# ganz `04 Ressourcen` — sonst wuerde jede Research-Notiz zum Kuerzeltraeger.
# "03 Bereiche" seit 2026-08-25 (E-08): der fuenfte Baum. Auch Bereichs-Hubs
# tragen Kuerzel — `BEREICH-A` an der Dozentur, `INSO` an der Privatinsolvenz.
# Das Register ist PARA-blind: es liest jede `.md` mit `meeting_key`/`lead_key`,
# gleich in welchem Baum sie liegt. Dass diese beiden Kuerzel bis dahin ins Leere
# liefen und ihre Meetings im Maschinen-Eingang landeten, lag allein an der
# fehlenden Wurzel hier, nicht an den Hubs.
# Warum nicht stattdessen nach `02 Projekte` verschieben: ein Bereich hat kein
# Enddatum, ein Projekt hat eines. Die Ablage nach dem Werkzeug zu richten hiesse,
# die Vault-Struktur zu verbiegen, damit ein Zeichenvergleich funktioniert. Also
# der umgekehrte Weg — der Baum kommt dazu.
# Anders als bei `04 Ressourcen` ist der Baum GANZ aufgenommen, nicht nur ein
# Unterordner: gemessen am 2026-08-25 tragen in `03 Bereiche` genau zwei Dateien
# einen Schluessel, beides Hubs. Es gibt hier keine Notizgattung, die durch die
# Aufnahme versehentlich zum Kuerzeltraeger wuerde.
REGISTER_WURZELN = ("02 Projekte", "09 Vertrieb", "10 Personen",
                    "04 Ressourcen/Persönliche Notizen", "03 Bereiche")

# Ablageort der flachen Kontakt-Notizen, relativ zur Vault-Wurzel.
KONTAKTE_ORDNER = os.path.join("09 Vertrieb", "_Kontakte")


def vault_wurzel():
    """Ort des Vaults — fester Pfad mit Override, keine Ableitung aus dem eigenen Ort.

    Bis zum 2026-08-06 lag dieses Skript im Vault, drei Ebenen unter der Wurzel; die
    Ableitung ueber `__file__` war deshalb korrekt. Seither wohnt der Code in einem
    eigenen Repo (Notizen-Strecke) und das Vault im privaten vault-Repo —
    die Ableitung zeigte danach ins Leere. `VAULT_DIR` bleibt als Override, damit ein
    Test nicht den echten Bestand anfasst."""
    return os.environ.get("VAULT_DIR", "/opt/vault")


def lade_register(vault):
    """Liest `meeting_key` und `lead_key` aus allen Baeumen — Projekt-Hubs,
    Lead-Hubs, Personen-Hubs, Themen-Hubs, seit E-08 auch Bereichs-Hubs — und
    inzwischen auch aus flachen Kontakt-Notizen in `_Kontakte/`. Das Vault ist die
    Quelle, nicht eine zweite gepflegte Liste — sonst driften beide auseinander.

    Fehlt einer der Baeume, wird er still uebersprungen: ein Vault ohne
    `09 Vertrieb` ist kein Fehlerfall, sondern ein Vault ohne Leads."""
    register = {}
    kollisionen = []
    for wurzel_name in REGISTER_WURZELN:
        wurzel = os.path.join(vault, wurzel_name)
        if not os.path.isdir(wurzel):
            continue
        for r, dirs, fs in os.walk(wurzel):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in fs:
                if not f.endswith(".md"):
                    continue
                p = os.path.join(r, f)
                try:
                    with open(p, encoding="utf-8") as fh:
                        kopf = fh.read(4096)
                except OSError:
                    continue
                m = FRONTMATTER_KEY.search(kopf)
                if not m:
                    continue
                k = m.group(1)
                ordner = os.path.relpath(r, vault)
                # Flache Kontakt-Notiz als Kuerzeltraeger (E-08):
                # Ziel ist der kuenftige Personen-Ordner, nicht `_Kontakte/`.
                if ordner == KONTAKTE_ORDNER:
                    ordner = os.path.join("10 Personen", os.path.splitext(f)[0])
                if k in register and register[k] != ordner:
                    kollisionen.append((k, register[k], ordner))
                else:
                    register[k] = ordner
    return register, kollisionen


def ordne_zu(titel, register):
    """Gibt (zielordner, grund) zurueck. zielordner=None heisst Maschinen-Eingang.

    Es wird NICHT geraten. Weder ueber Aehnlichkeit noch ueber Teiltreffer. Ein
    unbekanntes Kuerzel ist ein Befund, keine Einladung zur Interpretation."""
    if not titel or not titel.strip():
        return None, "leerer Titel"

    m = KUERZEL_MUSTER.match(titel)
    if not m:
        return None, "kein Kuerzel im Titel (erwartet: '[KUERZEL] Thema')"

    kuerzel, thema = m.group(1), m.group(2).strip()

    if kuerzel not in register:
        return None, f"Kuerzel '{kuerzel}' ist im Vault nicht vergeben"

    if not thema:
        return None, f"Kuerzel '{kuerzel}' erkannt, aber kein Thema im Titel"

    # Ein nacktes Stamm-Kuerzel darf laut Vault-Konvention nicht vergeben sein,
    # wenn es Praefix eines zweistufigen ist. Hier trotzdem pruefen: waere die
    # Konvention verletzt, ist die Zuordnung mehrdeutig und wir halten an.
    mehrdeutig = [k for k in register if k != kuerzel and k.startswith(kuerzel + "-")]
    if mehrdeutig:
        return None, (f"'{kuerzel}' ist Praefix von {sorted(mehrdeutig)} — mehrdeutig, "
                      f"Konvention verletzt")

    return register[kuerzel], f"Kuerzel '{kuerzel}' -> {register[kuerzel]}"


def selbsttest(register):
    """Prueft das Verhalten gegen echte und erfundene Titel. Wichtig sind die
    Negativfaelle: der Zuordner muss anhalten, nicht raten."""
    if not register:
        print("FEHLER: Register leer, Selbsttest nicht aussagekraeftig")
        return 1

    echtes = sorted(register)[0]
    faelle = [
        (f"[{echtes}] Ein echtes Thema", True, "bekanntes Kuerzel"),
        ("[ZZZZ] Unbekanntes Kuerzel", False, "unbekanntes Kuerzel darf nicht zugeordnet werden"),
        ("Besprechung ohne Kuerzel", False, "kein Kuerzel"),
        ("", False, "leerer Titel"),
        (f"[{echtes}]", False, "Kuerzel ohne Thema"),
        (f"Vorne Text [{echtes}] Thema", False, "Kuerzel nicht am Anfang"),
        (f"[{echtes.lower()}] Kleinschreibung", False, "Kuerzel muss gross sein"),
    ]

    fehler = 0
    print(f"Register: {len(register)} Kuerzel\n")
    print(f"{'Titel':<45} {'erwartet':<12} {'Ergebnis'}")
    print("-" * 92)
    for titel, soll_zuordnen, was in faelle:
        ziel, grund = ordne_zu(titel, register)
        ist = ziel is not None
        ok = (ist == soll_zuordnen)
        if not ok:
            fehler += 1
        anzeige = (titel[:43] + "..") if len(titel) > 45 else (titel or "(leer)")
        print(f"{anzeige:<45} {'zuordnen' if soll_zuordnen else 'Eingang':<12} "
              f"{'OK ' if ok else 'FEHLER '}— {grund}")
    print("-" * 92)
    print(f"{len(faelle) - fehler} von {len(faelle)} Faellen wie erwartet")
    return 1 if fehler else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--titel", help="Session-Titel aus der Transkript-Dienst")
    ap.add_argument("--selbsttest", action="store_true")
    ap.add_argument("--register", action="store_true", help="Register ausgeben")
    a = ap.parse_args()

    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 1

    register, kollisionen = lade_register(vault)

    if kollisionen:
        print("WARNUNG: Kuerzel doppelt vergeben — Zuordnung waere mehrdeutig:",
              file=sys.stderr)
        for k, a1, a2 in kollisionen:
            print(f"  {k}: {a1}  UND  {a2}", file=sys.stderr)

    if a.register:
        for k in sorted(register):
            print(f"{k}\t{register[k]}")
        return 0

    if a.selbsttest:
        return selbsttest(register)

    if not a.titel:
        ap.print_help()
        return 64

    ziel, grund = ordne_zu(a.titel, register)
    if ziel:
        print(f"ZUORDNUNG\t{ziel}\t{grund}")
        return 0
    print(f"EINGANG\t—\t{grund}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
