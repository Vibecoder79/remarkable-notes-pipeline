#!/usr/bin/env python3
"""Entfernt Infrastruktur-, Personen- und Ticket-Bezuege aus den kopierten Skripten.

Geordnete Liste: laengere Muster zuerst, sonst frisst eine kurze Regel die lange.
Trockenlauf ist die Vorgabe; --schreiben fuehrt aus.
"""
import argparse
import difflib
import re
import sys
from pathlib import Path

# ADR-Nummern des Hauses -> Entscheidungs-Dokumente dieses Repos.
ADR = {
    "E-01": "E-01",  # Zeiger statt Inhalt
    "E-02": "E-02",  # Drei Klassen von Eingriffen
    "E-03": "E-03",  # Fehlerklassen und Idempotenz
    "E-03": "E-03",
    "E-04": "E-04",  # Fremdinhalt ist Material
    "E-05": "E-05",  # Binaerdokumente durchsuchbar
    "E-06": "E-06",  # Stille bedeutet gesund
    "E-07": "E-07",  # Verknuepfen und melden statt fragen
    "E-08": "E-08",  # Kuerzel-Baeume
    "E-08": "E-08",
    "E-08": "E-08",
    "E-08": "E-08",
    "E-08": "E-08",
    "E-09": "E-09",  # Zwei App-Registrierungen
    "E-01": "E-01",
    "E-08": "E-08",
    "E-01": "E-01",
    "E-04": "E-04",
    "E-06": "E-06",
    "E-04": "E-04",
    "E-10": "E-10",  # Doku-Aufteilung
    "E-10": "E-10",
    "E-08": "E-08",
    "E-08": "E-08",
    "E-08": "E-08",
    "E-11": "E-11",  # Rueckweg
    "E-01": "E-01",
    "E-06": "E-06",
    "E-01": "E-01",
    "E-10": "E-10",
    "E-08": "E-08",
    "E-10": "E-10",
    "E-12": "E-12",  # Modellwahl explizit
    "E-12": "E-12",
    "E-13": "E-13",  # Betriebsumgebung
    "E-03": "E-03",
    "E-04": "E-04",
    "E-06": "E-06",
    "E-08": "E-08",
    "E-07": "E-07",
}

# Wortweise Ersetzungen, laengste zuerst.
WOERTER = [
    # --- Adressen und Domaenen ---
    ("notizen@example.com", "notizen@example.com"),
    ("tablet@example.com", "tablet@example.com"),
    ("eigner@example.com", "eigner@example.com"),
    ("contoso.sharepoint.com", "contoso.sharepoint.com"),
    ("@example.com", "@example.com"),
    ("example.com", "example.com"),
    ("BEISPIEL", "BEISPIEL"),
    ("Beispiel", "Beispiel"),
    ("beispiel", "beispiel"),
    # --- Pfade ---
    ("/opt/vault", "/opt/vault"),
    ("/etc/notizen-strecke/postfach.env", "/etc/notizen-strecke/postfach.env"),
    ("/etc/notizen-strecke", "/etc/notizen-strecke"),
    ("/var/log/notizen-strecke", "/var/log/notizen-strecke"),
    ("/var/lock/vault-schreiben.lock", "/var/lock/vault-schreiben.lock"),
    ("/var/lib/notizen-strecke/waechter-stand.json", "/var/lib/notizen-strecke/waechter-stand.json"),
    ("/var/lib/notizen-strecke/sprachnotiz-stand.json", "/var/lib/notizen-strecke/sprachnotiz-stand.json"),
    ("/var/lib/notizen-strecke/vorschlaege", "/var/lib/notizen-strecke/vorschlaege"),
    ("/opt/notizen-strecke", "/opt/notizen-strecke"),
    ("/var/lib/notizen-strecke", "/var/lib/notizen-strecke"),
    # --- Konten und Maschinen ---
    ("jobs", "jobs"),
    ("Notizen-Strecke", "Notizen-Strecke"),
    ("Notizen-Strecke", "Notizen-Strecke"),
    ("Automation", "Automation"),
    ("Melder", "Melder"),
    ("Vault", "Vault"),
    ("postfach.env", "postfach.env"),
    ("vault", "vault"),
    # --- Fremde Produkte und Traeger ---
    ("app.transkript-dienst.example", "app.transkript-dienst.example"),
    ("TRANSKRIPT_SESSION_URL", "TRANSKRIPT_SESSION_URL"),
    ("Transkript-Abholer", "Transkript-Abholer"),
    ("Sitzungstitel des Transkript-Dienstes", "Sitzungstitel des Transkript-Dienstes"),
    ("Sitzung des Transkript-Dienstes", "Sitzung des Transkript-Dienstes"),
    ("Sprachnotiz", "Sprachnotiz"),
    ("Transkript-Notiz", "Transkript-Notiz"),
    ("Transkript-Anbindung", "Transkript-Anbindung"),
    ("Web-App des Transkript-Dienstes", "Web-App des Transkript-Dienstes"),
    ("API des Transkript-Dienstes", "API des Transkript-Dienstes"),
    ("transkript_abholer", "transkript_abholer"),
    ("der Transkript-Dienst", "der Transkript-Dienst"),
    ("transkript", "transkript"),
    # --- Beispiel-Kuerzel und Namen ---
    ("ACME", "ACME"),
    ("Acme", "Acme"),
    ("VTR-ACME", "VTR-ACME"),
    ("P-MUSTER-M", "P-MUSTER-M"),
    ("[PROJ]", "[PROJ]"),
    ("Beispiel AG", "Beispiel AG"),
    ("BEREICH-A", "BEREICH-A"),
    ("ein Bereich", "ein Bereich"),
    ("BEREICH-A", "BEREICH-A"),
    ("der Eigner", "der Eigner"),
    ("Skizze", "Skizze"),
]


def adr_ersetzen(text):
    def ersetze(treffer):
        nr = treffer.group(0)
        return ADR.get(nr, "E-14")
    return re.sub(r"\bADR-\d{3}\b", ersetze, text)


def per_entfernen(text):
    """Linear-Ticketnummern raus. Sie zeigen auf ein Backlog, das niemand ausser
    dem Haus sieht — fuer einen Nachbauer sind sie Rauschen."""
    # Ganze Klammern, die NUR aus Ticketnummern bestehen.
    # `[ \t]*` statt `\s*`: sonst frisst die Regel den Zeilenumbruch VOR der Klammer
    # und die Datei verliert eine Zeile. Im zweiten Trockenlauf gemessen (432 -> 431).
    text = re.sub(r"[ \t]*\(PER-\d+(?:[ \t]*(?:,|und|bis|–|-)[ \t]*PER-\d+)*\)", "", text)
    # Ticketnummer als Zusatz in einer groesseren Klammer.
    text = re.sub(r",[ \t]*PER-\d+(?:[ \t]*(?:,|und|bis)[ \t]*PER-\d+)*", "", text)
    text = re.sub(r"PER-\d+(?:[ \t]*(?:,|und|bis)[ \t]*PER-\d+)*[ \t]*,[ \t]*", "", text)
    text = re.sub(r"\bPER-\d+\b", "", text)
    return text


# Der Platzhalter, den `per_entfernen` fuer eine Ticketnummer einsetzt.
# Als Variable und nicht woertlich in den Mustern unten: Liefe dieses Skript je
# ueber sich selbst, ersetzte es die Muster durch ihr eigenes Ergebnis und die
# Liste waere still eine Identitaetsabbildung. Genau das ist einmal passiert —
# uebrig blieb die Regel ("ab\\n", "ab dem Sprachnotiz-Zweig\\n"), die jedes
# Zeilenende «ab» getroffen haette. Siehe AUS in main().
P = "der Bau dieser Stufe"

# Die Ticketnummern standen mitten in Saetzen. Eine einzige Ersatzphrase ergibt
# darum Grammatikmuell («ab der Bau dieser Stufe zum Eingabetext»). Diese Liste
# glaettet die Faelle einzeln — laengste Muster zuerst.
GLAETTEN = [
    (f". {P}.", "."),
    (f" {P} Stufe 1", " Stufe 1"),
    (f"{P} Stufe 1:", "Stufe 1:"),
    (f"({P} Schritt 1)", "(Einrichtung, Schritt 1)"),
    (f"({P}-Muster)", "(bewaehrtes Muster)"),
    (f"{P} (Sperre) (Nachernte).", "Die Vault-Sperre."),
    (f"Grundlage: {P} (Eigner-Entscheid", "Grundlage: Eigner-Entscheid ("),
    (f"Grundlage: Rueckweg-Design aus {P}", "Grundlage: Rueckweg-Design"),
    (f"Einrichtung nach {P} pruefen", "Einrichtung der Bibliothek pruefen"),
    (f"seit {P} auch aus", "inzwischen auch aus"),
    (f"ab {P}\n", "ab dem Sprachnotiz-Zweig\n"),
    (f"Diktat-Texttest aus {P})", "Diktat-Texttest)"),
    (f"zu {P} hing", "dazu hing"),
    (f"({P})", ""),
    (f"{P}).", "der Einrichtung)."),
    (f" {P}", ""),
    (P, ""),
]

# Schaeden, die eine WORTweise Ersetzung anrichtet, weil das Muster als Substring
# in einem harmlosen Wort steckt. Wird NACH den Woertern angewandt.
NACHBESSERN = [
    # "beispiel" steckt in "Allowlist" — daraus wurde "Allowlist".
    ("Allowlist", "Allowlist"),
    ("allowlist", "allowlist"),
    # Env-Namen tragen den Systemnamen; sie muessen zur Doku passen.
    ("NOTIZEN_", "NOTIZEN_"),
    ("NOTIZEN_POSTFACH", "NOTIZEN_POSTFACH"),
    # Kontoname des Eigners, in Betriebshinweisen.
    ("Konto eigner", "Konto eigner"),
    ("eigner und jobs", "eigner und jobs"),
    ("eigner", "eigner"),
    # Echter Personenname aus den Proben.
    ("Muster Martina", "Muster Martina"),
    ("Muster", "Muster"),
]


def aufraeumen(zeile, original):
    """Kosmetik NACH dem Ersetzen — und nur dort, wo sie nichts kaputt macht.

    Zwei Regeln, die hier NICHT stehen duerfen, beide teuer gelernt:

    `re.sub(r"\\(\\s*\\)", "", text)` sollte leere Klammern aus Prosa entfernen und
    machte aus jedem `def postfach():` ein `def postfach:` — zehn von zwoelf Modulen
    liessen sich danach nicht mehr importieren.

    `re.sub(r"[ \\t]{2,}", " ", text)` sollte doppelte Leerzeichen zusammenziehen und
    traf jede absichtliche Ausrichtung: Tabellen in Docstrings, Spalten in
    Aufruf-Beispielen, 161 Zeilen insgesamt. Deshalb greift sie hier nur, wenn an
    dieser Stelle vorher KEIN Doppelleerzeichen stand — also nur bei Luecken, die
    das Ersetzen selbst gerissen hat.

    Eine Regel, die Prosa meint und Code trifft, gehoert nicht in einen Textersetzer.
    """
    if zeile == original:
        return zeile.rstrip()
    einzug = re.match(r"^[ \t]*", zeile).group(0)
    rumpf = zeile[len(einzug):]
    rumpf = re.sub(r"\(\s*,\s*", "(", rumpf)
    rumpf = re.sub(r"\s+,", ",", rumpf)
    # Nur zusammenziehen, wenn die ORIGINALZEILE dort keine Ausrichtung hatte.
    if "  " not in original.strip():
        rumpf = re.sub(r"[ \t]{2,}(?=\S)", " ", rumpf)
    return (einzug + rumpf).rstrip()


def sanitisiere(text):
    ersetzt = text
    for alt, neu in WOERTER:
        ersetzt = ersetzt.replace(alt, neu)
    ersetzt = adr_ersetzen(ersetzt)
    ersetzt = per_entfernen(ersetzt)
    for alt, neu in NACHBESSERN:
        ersetzt = ersetzt.replace(alt, neu)
    for alt, neu in GLAETTEN:
        ersetzt = ersetzt.replace(alt, neu)

    # Zeilenweise aufraeumen, damit jede Zeile ihr Original kennt. Die
    # Ersetzungen oben aendern keine Zeilenzahl — die PER-Regeln sind
    # ausdruecklich auf `[ \t]` statt `\s` begrenzt, damit kein Zeilenumbruch
    # verschwindet. Sonst liefe die Paarung hier auseinander.
    a, b = text.split("\n"), ersetzt.split("\n")
    if len(a) != len(b):
        raise SystemExit(f"ABBRUCH: Zeilenzahl geaendert ({len(a)} -> {len(b)}). "
                         f"Eine Regel frisst Zeilenumbrueche.")
    return "\n".join(aufraeumen(zb, za) for za, zb in zip(a, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wurzel")
    ap.add_argument("--schreiben", action="store_true")
    a = ap.parse_args()

    # Nur Code. NICHT die Doku: Sie schreibt ueber die Suchmuster und enthaelt sie
    # deshalb zwangslaeufig — ein Lauf darueber machte aus dem Satz «X wurde zu Y»
    # ein «Y wurde zu Y». Und nicht dieses Werkzeug selbst, aus demselben Grund.
    AUS = ("docs", "werkzeuge", "einrichtung", ".git")

    gesamt = 0
    wurzel = Path(a.wurzel).resolve()
    for pfad in sorted(wurzel.rglob("*")):
        if not pfad.is_file() or pfad.suffix not in (".py", ".sh", ".md", ".txt", ".tsv"):
            continue
        if set(pfad.relative_to(wurzel).parts) & set(AUS) or pfad.name == "README.md":
            continue
        alt = pfad.read_text(encoding="utf-8")
        neu = sanitisiere(alt)
        if alt == neu:
            continue
        # difflib, nicht zip: zip vergleicht nach einer entfallenen Zeile Aepfel mit
        # Birnen und meldete deshalb 413 von 432 Zeilen als geaendert.
        alt_z, neu_z = alt.splitlines(), neu.splitlines()
        aenderungen = sum(1 for z in difflib.unified_diff(alt_z, neu_z, n=0)
                          if z.startswith("-") and not z.startswith("---"))
        if len(alt_z) != len(neu_z):
            print(f"  ACHTUNG {pfad.name}: Zeilenzahl {len(alt_z)} -> {len(neu_z)}")
        gesamt += aenderungen
        print(f"{pfad.relative_to(wurzel)}: {aenderungen} Zeile(n)")
        if a.schreiben:
            pfad.write_text(neu, encoding="utf-8")
    print(f"\n{'Geschrieben' if a.schreiben else 'TROCKENLAUF'}: {gesamt} geaenderte Zeilen.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
