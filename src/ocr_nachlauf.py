#!/usr/bin/env python3
"""Holt Text aus gescannten PDFs im Vault. Langsam, mit Zeitbudget.

Ergaenzt dokument_extrakt.py um den teuren Fall: PDFs ohne Textebene. Waehrend
pdftotext Millisekunden braucht, kostet OCR gemessene 13 Sekunden pro Seite
(200 dpi, eine vCPU). 70 solche PDFs im Vault, zusammen mehrere Stunden.

Deshalb ein Nachlauf mit Budget statt eines Durchlaufs: er arbeitet ab, was in
sein Zeitfenster passt, und macht in der naechsten Nacht weiter. Ist nichts zu
tun, endet er sofort.

GRENZE: ausschliesslich Dokumente IM Vault, wie bei dokument_extrakt.py. Kein
SharePoint, kein OneDrive, keine Symlinks nach draussen (E-05 §4).

Fortschritt liegt im Ergebnis, nicht in einer Zustandsdatei: ein angefangener
Auszug traegt `ocr_seiten_fertig`, und der naechste Lauf haengt ab dieser Seite
an. Nur FEHLSCHLAEGE brauchen ein Register — sonst verbrennt ein kaputtes PDF
jede Nacht dieselben Minuten und blockiert den Fortschritt.

Dieses Programm committet NICHT. Das macht der Wrapper, und zwar mit der Sperre
nur fuer die paar Sekunden des Commits — wer zwei Stunden lang sperrt, legt alle
anderen Jobs lahm.

Aufrufe:
    ocr_nachlauf.py --liste                    zeigen, was ansteht
    ocr_nachlauf.py --budget 600 --trockenlauf
    ocr_nachlauf.py --budget 7200
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime

DPI = 200          # gemessen: 300 dpi kostet doppelt so lang fuer 3 % mehr Text
SPRACHEN = "deu+eng"
MINDESTTEXT = 500
MAX_VERSUCHE = 3
AUSGENOMMEN = (".git", ".obsidian", "06 Archiv", "07 Anhänge", "__pycache__")


def vault_wurzel():
    """Ort des Vaults — fester Pfad mit Override, keine Ableitung aus dem eigenen Ort.

    Bis zum 2026-08-06 lag dieses Skript im Vault, drei Ebenen unter der Wurzel; die
    Ableitung ueber `__file__` war deshalb korrekt. Seither wohnt der Code in einem
    eigenen Repo (Notizen-Strecke) und das Vault im privaten vault-Repo —
    die Ableitung zeigte danach ins Leere. `VAULT_DIR` bleibt als Override, damit ein
    Test nicht den echten Bestand anfasst."""
    return os.environ.get("VAULT_DIR", "/opt/vault")


def register_datei(vault):
    """Nur Fehlschlaege. Liegt ausserhalb des Repos — Laufzeitdaten gehoeren
    nicht in die Versionsgeschichte."""
    if os.environ.get("OCR_STATE_FILE"):
        return os.environ["OCR_STATE_FILE"]
    basis = os.path.abspath(os.path.join(vault, "..", ".."))
    return os.path.join(basis, "ocr-state.json")


def lade(pfad):
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"fehlschlaege": {}}


def speichere(pfad, daten):
    tmp = pfad + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)
    os.replace(tmp, pfad)


def seitenzahl(pfad):
    try:
        r = subprocess.run(["pdfinfo", pfad], capture_output=True, timeout=30)
        m = re.search(r"^Pages:\s+(\d+)", r.stdout.decode("utf-8", "ignore"), re.M)
        return int(m.group(1)) if m else 0
    except Exception:
        return 0


def hat_textebene(pfad):
    try:
        r = subprocess.run(["pdftotext", "-layout", pfad, "-"],
                           capture_output=True, timeout=120)
        return len(r.stdout.decode("utf-8", "ignore").strip()) >= MINDESTTEXT
    except Exception:
        return True   # im Zweifel nicht anfassen


def auszug_pfad(pdf):
    ordner, datei = os.path.split(pdf)
    return os.path.join(ordner, f"{os.path.splitext(datei)[0]} — Volltext.md")


def fortschritt(auszug):
    """Wieviele Seiten sind schon drin? 0, wenn es die Datei nicht gibt."""
    if not os.path.exists(auszug):
        return 0
    try:
        with open(auszug, encoding="utf-8") as f:
            kopf = f.read(2000)
        m = re.search(r"^ocr_seiten_fertig:\s*(\d+)", kopf, re.M)
        return int(m.group(1)) if m else 0
    except OSError:
        return 0


def ocr_seite(pdf, nr, arbeitsordner):
    """Eine Seite rendern und erkennen. Gibt den Text zurueck, leer bei Fehler."""
    stamm = os.path.join(arbeitsordner, "s")
    r = subprocess.run(["pdftoppm", "-r", str(DPI), "-png", "-f", str(nr),
                        "-l", str(nr), pdf, stamm],
                       capture_output=True, timeout=300)
    if r.returncode != 0:
        return ""
    bilder = [f for f in os.listdir(arbeitsordner) if f.endswith(".png")]
    if not bilder:
        return ""
    bild = os.path.join(arbeitsordner, bilder[0])
    try:
        r = subprocess.run(["tesseract", bild, "-", "-l", SPRACHEN],
                           capture_output=True, timeout=300)
        return r.stdout.decode("utf-8", "ignore")
    finally:
        os.remove(bild)


def kopf_schreiben(pdf, seiten, fertig, projekt):
    datei = os.path.basename(pdf)
    stamm = os.path.splitext(datei)[0]
    vollstaendig = fertig >= seiten
    zeilen = [
        "---",
        "tags: [textauszug, maschinell, ocr]",
        "typ: quell-volltext",
        f'original: "[[{datei}]]"',
        "dokumentart: pdf-scan",
        f"seiten: {seiten}",
        f"ocr_seiten_fertig: {fertig}",
        f"vollstaendig: {'ja' if vollstaendig else 'nein'}",
    ]
    if projekt:
        zeilen.append(f'project: "[[{projekt}]]"')
    zeilen += [
        f"extrahiert: {datetime.now().strftime('%Y-%m-%d')}",
        f"werkzeug: tesseract {SPRACHEN} @ {DPI}dpi",
        "layer: roh",
        "source: claude",
        "chat_url: unbekannt",
        # Stufe 1: siehe dokument_extrakt.py — der Auszug traegt fremden
        # Text und ist Material, nie Auftrag (E-04).
        "provenance:",
        "  origin: ingested-external",
        "  classification: internal",
        "  status: neu",
        "---",
        "",
        f"# {stamm} — Volltext (OCR)",
        "",
        "> [!warning] Maschinelle Texterkennung aus einem Scan",
        f"> Erkannt aus `{datei}` mit tesseract. **Fehler sind zu erwarten** —",
        "> OCR verwechselt Zeichen, verliert Tabellenstruktur und scheitert an",
        "> Handschrift. Für alles, worauf es ankommt, das Original heranziehen.",
    ]
    if not vollstaendig:
        zeilen += [
            ">",
            f"> **Unvollständig: {fertig} von {seiten} Seiten.** Der nächste Lauf",
            "> setzt fort.",
        ]
    zeilen += ["", "---", ""]
    return "\n".join(zeilen)


def projekt_hub(vault, ordner):
    p = ordner
    while p.startswith(vault) and len(p) > len(vault):
        for f in os.listdir(p):
            if f.endswith(" - PMO HUB.md"):
                return f[:-3]
        p = os.path.dirname(p)
    return None


def finde_scans(vault, register):
    """PDFs ohne Textebene, die noch nicht fertig sind."""
    offen = []
    vreal = os.path.realpath(vault)
    for ordner, unter, dateien in os.walk(vault):
        unter[:] = [u for u in unter if u not in AUSGENOMMEN]
        if any(x in ordner for x in AUSGENOMMEN):
            continue
        for datei in sorted(dateien):
            if not datei.lower().endswith(".pdf"):
                continue
            pfad = os.path.join(ordner, datei)
            if not os.path.realpath(pfad).startswith(vreal + os.sep):
                continue                      # Symlink nach draussen
            rel = os.path.relpath(pfad, vault)
            eintrag = register["fehlschlaege"].get(rel)
            if eintrag and eintrag.get("versuche", 0) >= MAX_VERSUCHE:
                continue
            seiten = seitenzahl(pfad)
            if seiten == 0:
                continue
            fertig = fortschritt(auszug_pfad(pfad))
            if fertig >= seiten:
                continue
            if fertig == 0 and hat_textebene(pfad):
                continue                      # kein Scan, gehoert dokument_extrakt.py
            offen.append((pfad, rel, seiten, fertig))
    return offen


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--budget", type=int, default=7200, help="Sekunden, Default 7200")
    ap.add_argument("--trockenlauf", action="store_true")
    ap.add_argument("--liste", action="store_true", help="nur zeigen, was ansteht")
    a = ap.parse_args()

    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 1
    for werkzeug in ("pdftoppm", "tesseract", "pdfinfo"):
        if not shutil.which(werkzeug):
            print(f"ABBRUCH: '{werkzeug}' fehlt.", file=sys.stderr)
            return 127

    rpfad = register_datei(vault)
    register = lade(rpfad)

    print(f"Suche Scans … (das dauert, jedes PDF wird geprueft)")
    offen = finde_scans(vault, register)
    seiten_gesamt = sum(s - f for _, _, s, f in offen)
    print(f"{len(offen)} Dokumente offen, {seiten_gesamt} Seiten zu erkennen.")
    print(f"Geschaetzt: {seiten_gesamt * 13 // 60} Minuten bei 13 s/Seite.")

    if a.liste or not offen:
        for _, rel, s, f in offen[:30]:
            print(f"  {s - f:4d} Seiten offen  {rel}")
        if len(offen) > 30:
            print(f"  ... und {len(offen) - 30} weitere")
        return 0

    ende = time.time() + a.budget
    z = {"fertig": 0, "teilweise": 0, "fehler": 0, "seiten": 0}
    geschrieben = []

    for pfad, rel, seiten, schon in offen:
        if time.time() >= ende:
            print("\nZeitbudget erschoepft — der naechste Lauf macht weiter.")
            break

        print(f"\n  {rel}")
        print(f"    {seiten} Seiten, {schon} bereits erkannt")
        if a.trockenlauf:
            continue

        auszug = auszug_pfad(pfad)
        arbeit = tempfile.mkdtemp(prefix="ocr-")
        teile, nr, abgebrochen = [], schon + 1, False
        try:
            while nr <= seiten:
                if time.time() >= ende:
                    abgebrochen = True
                    break
                text = ocr_seite(pfad, nr, arbeit)
                if text.strip():
                    teile.append(f"\n\n<!-- Seite {nr} -->\n\n{text.strip()}")
                z["seiten"] += 1
                nr += 1
        finally:
            shutil.rmtree(arbeit, ignore_errors=True)

        fertig_bis = nr - 1
        if not teile and fertig_bis <= schon:
            # Nichts erkannt: kaputtes PDF, Fotos ohne Schrift, Handschrift
            e = register["fehlschlaege"].setdefault(rel, {"versuche": 0})
            e["versuche"] += 1
            e["zuletzt"] = datetime.now().isoformat(timespec="seconds")
            e["grund"] = "keine Zeichen erkannt"
            print(f"    nichts erkannt (Versuch {e['versuche']}/{MAX_VERSUCHE})")
            z["fehler"] += 1
            continue

        hub = projekt_hub(vault, os.path.dirname(pfad))
        kopf = kopf_schreiben(pfad, seiten, fertig_bis, hub)
        if schon and os.path.exists(auszug):
            with open(auszug, encoding="utf-8") as f:
                alt = f.read()
            rumpf = alt.split("\n---\n", 2)[-1]
            neu = kopf + rumpf.strip() + "".join(teile) + "\n"
        else:
            neu = kopf + "".join(teile).strip() + "\n"
        with open(auszug, "w", encoding="utf-8") as f:
            f.write(neu)
        geschrieben.append(os.path.relpath(auszug, vault))

        if fertig_bis >= seiten:
            print(f"    fertig, {fertig_bis} Seiten")
            z["fertig"] += 1
            register["fehlschlaege"].pop(rel, None)
        else:
            print(f"    unterbrochen bei Seite {fertig_bis} von {seiten}")
            z["teilweise"] += 1
        if abgebrochen:
            break

    if not a.trockenlauf:
        speichere(rpfad, register)

    print(f"\nFertig: {z['fertig']} | teilweise: {z['teilweise']} | "
          f"Fehler: {z['fehler']} | Seiten erkannt: {z['seiten']}")
    if a.trockenlauf:
        print("Trockenlauf — nichts geschrieben.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
