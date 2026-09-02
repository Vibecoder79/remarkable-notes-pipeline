#!/usr/bin/env python3
"""Ordnet PDFs aus der reMarkable-Bibliothek einem Baum zu und legt die Zeiger-Notiz an.

Grundlage: E-01 reMarkable-Anbindung §3 und §6 (praezisiert 2026-08-15:
Kuerzel-Raum ueber die Baeume aus REGISTER_WURZELN). Zuordnung ist Zeichenvergleich, keine
Interpretation — Klasse 2 nach E-02, also autonom und ohne Freigabe.

Was dieses Programm tut, je Bibliothekseintrag mit `Status = Neu`:
  1. Kuerzel aus dem DATEINAMEN lesen (`YYYY-MM-DD [KUERZEL] Thema.pdf`),
     ersatzweise aus der Spalte `Kontext` (dem Mailrumpf). Steht beides da,
     gewinnt der Name — keine zwei Wahrheiten.
  2. ueber `kuerzel_register.py` in einen Ordner aufloesen — in JEDEN Baum aus
     `REGISTER_WURZELN` — heute Projekt, Lead, Person, Persoenliche Notiz und
     Bereich (E-08). Diese Aufzaehlung stand hier einmal als feste Dreierliste
     und war damit schon zwei Baeume im Rueckstand; massgeblich ist die
     Konstante, nicht dieser Satz. Mit baumuebergreifender Kollisionspruefung.
     Wiederverwendet, nicht verdoppelt.
  3. Zeiger-Notiz in `<Ordner>/Notizen/` anlegen: Kontext als Text, `artefakt:`
     als Link auf das SharePoint-Dokument. NICHT das PDF ins Vault kopieren.
     Dazu die TEXTEBENE des PDFs: deterministisch mit `pdftotext`
     gezogen, auf 4'000 Zeichen gekappt und als Zitat gerahmt — das E-05-
     Muster (Binaerdokument -> durchsuchbarer Auszug). Erfasst wird nur
     getippter/diktierter/umgewandelter Text; Handschrift ist im PDF
     Vektorzeichnung und bleibt draussen, kein OCR. Die Zuordnung haengt NIE
     an der Textebene — sie liefert Kontext, das Routing bleibt am Dateinamen
     (E-01-Auflage).
  4. Bibliotheks-Spalten nachziehen: `Projekt`, `Vault-Notiz`, `Status = Verarbeitet`.
  5. Kein Kuerzel → keine Notiz. Der Eintrag bleibt `Neu` und erscheint in der
     Ansicht «Ohne Zuordnung», bis er per Umbenennen repariert wird.

Schreibt ins Vault — laeuft deshalb unter `mit-sperre.sh` und committet/schiebt.
Der Bibliothekszugriff laeuft ueber die Plattform-App (m365.env, Sites.Selected),
NICHT ueber die Postfach-App.

Aufrufe:
    remarkable_zuordner.py --pruefe-zugang
    remarkable_zuordner.py --trockenlauf
    remarkable_zuordner.py
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

from graph_basis import (DAUERHAFT, VORUEBERGEHEND, Fehler, geheimnis,
                                graph, graph_mit_kopf, graph_token)
from kuerzel_register import lade_register, ordne_zu
from vault_baeume import materialisiere_personen_ordner, sichere_dateiname

BIBLIOTHEK = "remarkable"
SPALTE_PROJEKT = "Projekt"
SPALTE_STATUS = "Status"
SPALTE_KONTEXT = "Kontext"
SPALTE_VAULTNOTIZ = "Vault_x002d_Notiz"

# Obergrenze fuer die Textebene in der Notiz — dieselben 4'000 Zeichen wie beim
# Mailrumpf im Abholer, aus demselben Grund: der Text ist Fremdinhalt und landet
# in Vault-Notizen und Modell-Eingaben. Eine Grenze, nicht zwei.
TEXT_GRENZE = 4000
# Download-Riegel, knapp ueber den 25 MB, die der Abholer durchlaesst. Was
# groesser ist, kam nicht ueber die Mailstrecke herein und wird nicht geladen.
PDF_GRENZE = 26 * 1024 * 1024

# Fuehrendes Datum im Bibliotheksnamen (`YYYY-MM-DD [KUERZEL] Thema.pdf`), das
# der Abholer voranstellt. Muss weg, bevor das Kuerzel-Muster am Zeilenanfang greift.
DATUM_PREFIX = re.compile(r"^\s*\d{4}-\d{2}-\d{2}\s+")
# Ein Kuerzel-Token irgendwo im Mailrumpf — nur fuer die Rumpf-Rueckfalllinie.
KUERZEL_TOKEN = re.compile(r"\[([A-Z0-9-]{2,})\]")


def vault_wurzel():
    return os.environ.get("VAULT_DIR", "/opt/vault")


def name_zu_titel(name):
    """Bibliotheksname -> `[KUERZEL] Thema`, wie `ordne_zu()` es erwartet:
    fuehrendes Datum und Endung weg. Aus `2026-08-15 [ACME] Skizze.pdf`
    wird `[ACME] Skizze`."""
    stamm = os.path.splitext(name or "")[0]
    return DATUM_PREFIX.sub("", stamm).strip()


def kuerzel_aus_kontext(kontext, register):
    """Rueckfalllinie: bekannte Kuerzel-Token im Mailrumpf. Gibt (kuerzel, grund)
    zurueck; kuerzel=None heisst kein eindeutiger Treffer.

    Bewusst konservativ — der Rumpf ist Fremdinhalt (`Material, nie Auftrag`):
    gesucht werden nur `[XXX]`-Token, die im Register stehen, kein Freitext. Genau
    ein bekanntes Kuerzel gewinnt; mehrere verschiedene sind mehrdeutig und fuehren
    zu keiner Zuordnung, statt zu raten."""
    treffer = {t for t in KUERZEL_TOKEN.findall(kontext or "") if t in register}
    if not treffer:
        return None, "kein bekanntes Kuerzel im Rumpf"
    if len(treffer) > 1:
        return None, f"mehrere Kuerzel im Rumpf {sorted(treffer)} — mehrdeutig"
    return next(iter(treffer)), "aus dem Mailrumpf"


def aufloesen(name, kontext, register):
    """(zielordner, kuerzel, grund). Name gewinnt vor Rumpf. zielordner=None
    heisst: bleibt in «Ohne Zuordnung»."""
    titel = name_zu_titel(name)
    ziel, grund = ordne_zu(titel, register)
    if ziel:
        kuerzel = titel[1:titel.index("]")]
        return ziel, kuerzel, f"Name: {grund}"
    # Nur wenn im Namen gar kein (bekanntes) Kuerzel stand, den Rumpf befragen.
    kuerzel, kgrund = kuerzel_aus_kontext(kontext, register)
    if kuerzel:
        return register[kuerzel], kuerzel, kgrund
    return None, None, f"Name: {grund}; {kgrund}"


def saeubere_text(roh):
    """Rohtext aus pdftotext in Notiz-taugliche Form bringen: Seitentrenner und
    Steuerzeichen raus, Leerzeilen zusammenziehen, auf TEXT_GRENZE kappen.
    Gibt (text, gesamt) zurueck — gesamt ist die Zeichenzahl VOR dem Kappen,
    damit die Notiz ehrlich sagen kann, was fehlt. (None, 0) heisst leer."""
    text = roh.replace("\f", "\n")
    text = "".join(z for z in text if z in "\n\t" or ord(z) >= 32)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return None, 0
    return text[:TEXT_GRENZE].rstrip(), len(text)


def pdf_textebene(daten):
    """Textebene eines PDFs ziehen — deterministisch mit pdftotext, kein Modell.

    (None, 0) heisst: keine Textebene, kein PDF oder Werkzeugfehler. Fuer reine
    Handschrift ist das der NORMALFALL — sie ist im Export Vektorzeichnung, und
    OCR gibt es hier bewusst nicht (ehrliche Grenze)."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(daten)
        tmp.flush()
        try:
            lauf = subprocess.run(["pdftotext", "-q", "-enc", "UTF-8", tmp.name, "-"],
                                  capture_output=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError):
            return None, 0
    if lauf.returncode != 0:
        return None, 0
    return saeubere_text(lauf.stdout.decode("utf-8", errors="replace"))


def hole_textebene(token, site, list_id, item_id):
    """Das PDF aus der Bibliothek laden und die Textebene ziehen.

    Geladen wird ueber `@microsoft.graph.downloadUrl` und OHNE Authorization-
    Kopf: Die URL ist kurzlebig vor-authentifiziert, und der Graph-Token gilt
    fuer graph.microsoft.com — die SharePoint-Download-Domain lehnt ihn ab,
    wenn er mitkommt. Deshalb nicht `graph_mit_kopf()` auf `/content`."""
    # Bewusst OHNE $select: Graph verwirft die downloadUrl-Annotation, sobald
    # ein $select dabei ist — am 2026-08-15 an dieser Bibliothek gemessen
    # (mit $select fehlt der Schluessel, ohne ist er da).
    meta = graph(token, "GET",
                 f"/sites/{site}/lists/{list_id}/items/{item_id}/driveItem")
    url = meta.get("@microsoft.graph.downloadUrl")
    if not url:
        raise Fehler(DAUERHAFT, "driveItem traegt keine downloadUrl.")
    if (meta.get("size") or 0) > PDF_GRENZE:
        raise Fehler(DAUERHAFT,
                     f"{meta['size']} Bytes — ueber dem Riegel von {PDF_GRENZE}. "
                     f"Ueber die Mailstrecke kam das nicht herein; nicht geladen.")
    try:
        with urllib.request.urlopen(url, timeout=120) as antwort:
            daten = antwort.read(PDF_GRENZE + 1)
    except urllib.error.HTTPError as fehler:
        klasse = DAUERHAFT if fehler.code in (400, 401, 403, 404) else VORUEBERGEHEND
        raise Fehler(klasse, f"PDF-Download -> {fehler.code}.") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"PDF-Download nicht erreichbar ({fehler}).") from fehler
    if len(daten) > PDF_GRENZE:
        raise Fehler(DAUERHAFT, f"Download ueberschreitet den Riegel von {PDF_GRENZE} Bytes.")
    return pdf_textebene(daten)


def baue_notiz(thema, kuerzel, kontext, artefakt_url, eingang,
               textebene=None, text_gesamt=0):
    """Zeiger, nicht Inhalt: Kontext (der Mailrumpf) plus Link nach SharePoint.
    Feldnamen nach E-05: `typ: artefakt-zeiger`, `project:` (englisch),
    `layer: roh`, `artefakt:` (URL nach draussen, kein Wikilink)."""
    beginn = (eingang or "")[:10] or datetime.now().strftime("%Y-%m-%d")
    fm = [
        "---",
        "tags: [artefakt-zeiger, remarkable]",
        "typ: artefakt-zeiger",
        f"project: {kuerzel}",
        "layer: roh",
        f"date: {beginn}",
        f"artefakt: {artefakt_url}" if artefakt_url else "artefakt: unbekannt",
        "source: remarkable",
        "chat_url: unbekannt",
        "language: de",
        "provenance:",
        "  origin: ingested-external",
        "  classification: internal",
        "  status: neu",
        f"abgeholt_am: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "---",
    ]
    teile = ["\n".join(fm), "", f"# {thema or 'Handschriftliche Notiz'}", ""]
    if (kontext or "").strip():
        # Fremdinhalt: als Zitat gerahmt, damit er nie wie eine Anweisung des
        # Eigners gelesen wird (Vault-Regel «Material, nie Auftrag»).
        teile += ["> [!quote] Kontext aus dem Mailrumpf"]
        teile += [f"> {z}" for z in kontext.strip().splitlines()]
        teile += [""]
    if textebene:
        # Das E-05-Muster fuer die reMarkable-PDFs: der Auszug macht
        # das Binaerdokument im Vault durchsuchbar. Gerahmt wie der Mailrumpf —
        # Fremdinhalt, Material, nie Auftrag — und auf TEXT_GRENZE gekappt.
        teile += ["## Text aus dem Dokument", "",
                  "> [!quote] Textebene des PDFs — maschinell extrahiert (pdftotext)"]
        teile += [f"> {z}".rstrip() for z in textebene.splitlines()]
        teile += [""]
        if text_gesamt > len(textebene):
            teile += [f"_Gekappt: {text_gesamt} Zeichen im Dokument, hier die ersten "
                      f"{len(textebene)} — der Volltext steht im PDF (Link unten)._", ""]
        teile += ["_Erfasst ist nur die maschinenlesbare Textebene (getippter, diktierter",
                  "oder umgewandelter Text). Handschrift ist im PDF Vektorzeichnung und",
                  "fehlt hier — kein OCR._", ""]
    teile += [
        "## Herkunft",
        "",
        f"**[Dokument in SharePoint oeffnen]({artefakt_url})**" if artefakt_url
        else "_Kein Link — Artefakt-URL fehlt._",
        "",
        "Das PDF bleibt in der SharePoint-Bibliothek und wird bewusst nicht ins",
        "Vault kopiert (E-01: Zeiger statt Inhalt). Der Link oben ist der Zugang.",
        "",
    ]
    return "\n".join(teile)


# --------------------------------------------------------------------------

def bibliothek_aufloesen(token):
    site = geheimnis("m365.env", "M365_SITE_ID")
    if not site:
        raise Fehler(DAUERHAFT, "M365_SITE_ID fehlt in m365.env.")
    r, _ = graph_mit_kopf(token, "GET", f"/sites/{site}/lists?$select=id,name")
    liste = next((l for l in r.get("value", [])
                  if (l.get("name") or "").lower() == BIBLIOTHEK), None)
    if not liste:
        raise Fehler(DAUERHAFT, f"Bibliothek '{BIBLIOTHEK}' nicht gefunden.")
    return site, liste["id"]


def neue_eintraege(token, site, list_id):
    """Alle Eintraege mit `Status = Neu`, mit Feldern und Datei-URL. Clientseitig
    gefiltert — die Bibliothek ist klein, ein Filter auf eine nicht indizierte
    Spalte waere fragiler als ihn hier zu ziehen."""
    r, _ = graph_mit_kopf(
        token, "GET",
        f"/sites/{site}/lists/{list_id}/items?$expand=fields,driveItem&$top=200")
    roh = r.get("value", [])
    frisch = []
    for it in roh:
        f = it.get("fields") or {}
        if (f.get(SPALTE_STATUS) or "") != "Neu":
            continue
        frisch.append({
            "id": it["id"],
            "name": f.get("FileLeafRef") or (it.get("driveItem") or {}).get("name") or "",
            "kontext": f.get(SPALTE_KONTEXT) or "",
            "eingang": f.get("Eingang") or "",
            "url": (it.get("driveItem") or {}).get("webUrl") or it.get("webUrl") or "",
        })
    return frisch


def spalten_nachziehen(token, site, list_id, item_id, kuerzel, vaultpfad):
    graph_mit_kopf(token, "PATCH",
                   f"/sites/{site}/lists/{list_id}/items/{item_id}/fields",
                   rumpf={SPALTE_PROJEKT: kuerzel,
                          SPALTE_VAULTNOTIZ: vaultpfad,
                          SPALTE_STATUS: "Verarbeitet"})


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pruefe-zugang", action="store_true")
    ap.add_argument("--trockenlauf", action="store_true", help="nichts schreiben")
    a = ap.parse_args()

    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 1

    try:
        token = graph_token()
        site, list_id = bibliothek_aufloesen(token)
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2

    if a.pruefe_zugang:
        print(f"Bibliothek '{BIBLIOTHEK}' erreichbar (Liste {list_id[:8]}…).")
        return 0

    register, kollisionen = lade_register(vault)
    if kollisionen:
        print("WARNUNG: Kuerzel doppelt vergeben — betroffene bleiben unzugeordnet:",
              file=sys.stderr)
        for k, a1, a2 in kollisionen:
            print(f"  {k}: {a1}  UND  {a2}", file=sys.stderr)
    print(f"Register: {len(register)} Kuerzel ueber die Baeume.")

    try:
        eintraege = neue_eintraege(token, site, list_id)
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2
    print(f"{len(eintraege)} Eintrag(e) mit Status=Neu.")

    zaehler = {"zugeordnet": 0, "ohne": 0, "schon_da": 0, "vertagt": 0}
    geschrieben = []

    for e in eintraege:
        ziel_rel, kuerzel, grund = aufloesen(e["name"], e["kontext"], register)
        if not ziel_rel:
            print(f"  [OHNE   ] {e['name']} — {grund}")
            zaehler["ohne"] += 1
            continue

        thema = name_zu_titel(e["name"])
        thema = thema[thema.index("]") + 1:].strip() if "]" in thema else thema
        notiz_name = f"{sichere_dateiname(os.path.splitext(e['name'])[0])}.md"
        ordner_rel = os.path.join(ziel_rel, "Notizen")
        pfad = os.path.join(vault, ordner_rel, notiz_name)
        pfad_rel = os.path.join(ordner_rel, notiz_name)
        print(f"  [ZUORDNEN] {e['name']} -> {ordner_rel}  ({grund})")

        # Textebene des PDFs — nur fuer neue Notizen; eine vorhandene
        # Notiz wird nie angefasst (Handarbeit). Laeuft auch im Trockenlauf,
        # damit sich am echten Dokument MESSEN laesst, ob eine Textebene da ist
        # (Diktat-Texttest), ohne etwas zu schreiben.
        schon_da = os.path.exists(pfad)
        textebene, text_gesamt = None, 0
        if not schon_da:
            try:
                textebene, text_gesamt = hole_textebene(token, site, list_id, e["id"])
            except Fehler as fehler:
                if fehler.klasse == VORUEBERGEHEND:
                    # Die Notiz gibt es noch nicht — nichts geht verloren, wenn
                    # der naechste Lauf (15 Min) alles inklusive Text nachholt.
                    print(f"             VERTAGT: {fehler} Eintrag bleibt Neu.",
                          file=sys.stderr)
                    zaehler["vertagt"] += 1
                    continue
                # Erneut versuchen hilft nie — die Notiz entsteht ohne Text,
                # der Zeiger ist die Hauptsache, der Auszug die Zugabe.
                print(f"             WARNUNG: keine Textebene ({fehler})",
                      file=sys.stderr)
            if textebene:
                zusatz = (f", gekappt auf {len(textebene)}"
                          if text_gesamt > len(textebene) else "")
                print(f"             Textebene: {text_gesamt} Zeichen{zusatz}.")
            else:
                print("             Textebene: keine — bei reiner Handschrift "
                      "der Normalfall (Vektorzeichnung, kein OCR).")

        if a.trockenlauf:
            # Personen-Materialisierung im Trockenlauf nur ankuendigen.
            m_meldung, _ = materialisiere_personen_ordner(vault, ziel_rel, True)
            if m_meldung:
                print(f"             {m_meldung}")
            continue

        # Personen-Ordner beim ersten Inhalt materialisieren (E-08) —
        # dieselbe Mechanik wie beim Transkript-Abholer.
        m_meldung, m_pfade = materialisiere_personen_ordner(vault, ziel_rel, False)
        if m_meldung:
            print(f"             {m_meldung}")
        geschrieben.extend(m_pfade)

        os.makedirs(os.path.join(vault, ordner_rel), exist_ok=True)
        if schon_da:
            # Wiederaufnahme nach Teilabbruch: Notiz liegt schon, nur die Spalten
            # fehlten. Handarbeit nie ueberschreiben.
            print("             Notiz existiert bereits — nur Spalten nachziehen.")
            zaehler["schon_da"] += 1
        else:
            with open(pfad, "w", encoding="utf-8") as fh:
                fh.write(baue_notiz(thema, kuerzel, e["kontext"], e["url"], e["eingang"],
                                    textebene, text_gesamt))
            geschrieben.append(pfad_rel)
            zaehler["zugeordnet"] += 1

        try:
            spalten_nachziehen(token, site, list_id, e["id"], kuerzel, pfad_rel)
        except Fehler as fehler:
            print(f"             WARNUNG: Spalten nicht gesetzt ({fehler}) — "
                  f"Notiz liegt, Eintrag bleibt Neu und wird erneut versucht.",
                  file=sys.stderr)

    print(f"\nZugeordnet: {zaehler['zugeordnet']}, ohne Zuordnung: {zaehler['ohne']}, "
          f"bereits da: {zaehler['schon_da']}, vertagt: {zaehler['vertagt']}.")

    if a.trockenlauf:
        print("Trockenlauf — nichts geschrieben.")
        return 0
    return veroeffentliche(vault, geschrieben)


def veroeffentliche(vault, pfade):
    """Committen und pushen — sonst sieht der Eigner die Notizen nie (Mac-Klon).
    Reihenfolge zwingend: erst ziehen (--ff-only), dann committen, dann schieben."""
    if not pfade:
        print("Nichts geschrieben, kein Commit.")
        return 0

    def git(*args):
        return subprocess.run(["git", "-C", vault, *args], capture_output=True, text=True)

    if git("pull", "--ff-only", "origin", "main").returncode != 0:
        print("WARNUNG: pull --ff-only fehlgeschlagen — Arbeitskopie haengt zurueck.",
              file=sys.stderr)
        return 1
    git("add", "--", *pfade)
    n = len(pfade)
    kopf = f"chore(remarkable): {n} Zeiger-Notiz{'en' if n != 1 else ''} zugeordnet"
    if git("commit", "-q", "-m", kopf, "-m", "\n".join(f"- {p}" for p in pfade)).returncode != 0:
        print("Nichts zu committen.")
        return 0
    if git("push", "-q", "origin", "main").returncode != 0:
        print("WARNUNG: Push fehlgeschlagen. Committet, aber nicht beim Mac.", file=sys.stderr)
        return 1
    print(f"Veroeffentlicht: {git('rev-parse', '--short', 'HEAD').stdout.strip()} ({n})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
