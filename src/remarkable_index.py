#!/usr/bin/env python3
"""Kuerzel-Index fuer das reMarkable — PDF erzeugen und in die Bibliothek legen.

Grundlage: Rueckweg-Design (Research 2026-08-15). Deterministisch,
kein Sprachmodell: Das Register kommt aus `kuerzel_register.lade_register()` — dieselbe
Quelle, gegen die der Zuordner Dateinamen aufloest. Eine zweite Kuerzelliste gaebe es
damit nicht; was der Index zeigt, ist exakt das, was die Strecke versteht.

Der Index ist der Nachschlage-Zettel gegen die einzige echte Schwachstelle der
Strecke: den Tippfehler beim Kuerzel (-> «Ohne Zuordnung»). Oben steht die
Namensregel, darunter alle Kuerzel gruppiert nach den Baeumen (Projekte / Vertrieb / Personen / Persoenliche Notizen),
je Gruppe alphabetisch.

PDF-Erzeugung mit fpdf2 (Ubuntu-Paket `python3-fpdf`, reines Python) — die kleinste
Abhaengigkeit, die Unicode-TTF einbetten kann: Die Ordnernamen tragen Umlaute, und
der eingebaute Latin-1-Zeichensatz von PDF reicht dafuer nicht. LibreOffice oder
reportlab waeren auf 1 vCPU / 4 GB unverhaeltnismaessig. Schrift: DejaVu Sans aus
dem Systembestand (`fonts-dejavu-core`).

Ablage: Bibliothek `an-remarkable` auf der Site «Automation» — bewusst
getrennt von der Abhol-Bibliothek `remarkable`, damit Hin- und Rueckweg nicht
vermischen. Flach, keine Spalten. Stabiler Dateiname, jeder Lauf ueberschreibt:
am Geraet ist es immer dieselbe, aktuelle Datei. Die Bibliothek legt der Eigner von
Hand an — `Sites.Selected` kann kein Schema (403 gemessen am 2026-08-16, Falle 4
der reMarkable-Doku gilt auch fuer die Listen-Anlage). Fehlt sie beim Lauf, wird
VORUEBERGEHEND vertagt, nicht abgestuerzt: der naechste Lauf nach der Anlage heilt.

Aufrufe:
    remarkable_index.py                      erzeugen und hochladen
    remarkable_index.py --trockenlauf        erzeugen, nichts hochladen
    remarkable_index.py --ausgabe X.pdf      nur lokal schreiben, kein Graph
    remarkable_index.py --pruefe-zugang      Bibliothek erreichbar?
    remarkable_index.py --schreibprobe       Testdatei hochladen, lesen, loeschen
"""
import argparse
import datetime
import json
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_basis import (DAUERHAFT, VORUEBERGEHEND, Fehler, geheimnis,
                                graph_mit_kopf, graph_token)
from kuerzel_register import lade_register, vault_wurzel

BIBLIOTHEK = "an-remarkable"
DATEINAME = "Vault — Kürzel-Index.pdf"

# Anzeige-Reihenfolge der Baeume. Der Schluessel ist die Vault-Wurzel des
# Baums, wie sie in den Registerwerten steht (kuerzel_register.REGISTER_WURZELN).
# Diese Liste muss jeden Baum von dort kennen: fehlt einer, landen seine Kuerzel
# in der Auffanggruppe «Ausserhalb der Bäume» — sie verschwinden nicht, aber die
# Ueberschrift wird zur Falschaussage. Genau das war am 2026-08-25 fuer eine
# Stunde der Fall, als `03 Bereiche` ins Register kam und hier noch fehlte.
# "03 Bereiche" seit 2026-08-25 (E-08).
BAEUME = (("02 Projekte", "Projekte"),
          ("09 Vertrieb", "Vertrieb"),
          ("10 Personen", "Personen"),
          ("04 Ressourcen/Persönliche Notizen", "Persönliche Notizen"),
          ("03 Bereiche", "Bereiche"))

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def gruppieren(register):
    """Register (kuerzel -> vault-relativer Ordner) in die Baeume sortieren.

    Rueckgabe: Liste (anzeigename, [(kuerzel, ordnername), ...]) in fester
    Baum-Reihenfolge, je Gruppe alphabetisch nach Kuerzel. Der Ordnername ist der
    Pfad RELATIV zur Baum-Wurzel — bei verschachtelten Ablagen (Kunden-Ordner,
    Vertriebs-Jahrgang) traegt die Zwischenebene Information, also bleibt sie."""
    gruppen = {wurzel: [] for wurzel, _ in BAEUME}
    uebrig = []
    for kuerzel in sorted(register):
        ordner = register[kuerzel].replace("\\", "/")
        for wurzel, _ in BAEUME:
            if ordner == wurzel or ordner.startswith(wurzel + "/"):
                rel = ordner[len(wurzel):].lstrip("/") or wurzel
                gruppen[wurzel].append((kuerzel, rel))
                break
        else:
            uebrig.append((kuerzel, ordner))
    ergebnis = [(name, gruppen[wurzel]) for wurzel, name in BAEUME]
    if uebrig:
        # Kein bekannter Baum — duerfte nicht vorkommen, wird aber gezeigt statt
        # verschluckt: ein Kuerzel, das im Index fehlt, waere genau die Luecke,
        # die der Index schliessen soll.
        ergebnis.append(("Ausserhalb der Bäume", uebrig))
    return ergebnis


def pdf_bauen(gruppen, ziel_pfad, stand=None):
    """Das PDF rendern — deterministisch, ohne Netz. `stand` ist der Zeitstempel
    fuer die Fusszeile (Standard: jetzt)."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    for schrift in ("DejaVuSans.ttf", "DejaVuSans-Bold.ttf"):
        if not (FONT_DIR / schrift).is_file():
            raise Fehler(DAUERHAFT,
                         f"Schrift '{schrift}' fehlt unter {FONT_DIR} — "
                         f"Paket fonts-dejavu-core installieren.")

    stand = stand or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    gesamt = sum(len(eintraege) for _, eintraege in gruppen)

    class Index(FPDF):
        def footer(self):
            self.set_y(-14)
            self.set_font("DejaVu", "", 8)
            self.set_text_color(120)
            self.cell(0, 6, f"Stand {stand} — {gesamt} Kürzel — Seite "
                            f"{self.page_no()}/{{nb}}", align="C")
            self.set_text_color(0)

    pdf = Index(orientation="P", format="A4")
    pdf.add_font("DejaVu", "", str(FONT_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(FONT_DIR / "DejaVuSans-Bold.ttf"))
    pdf.set_title("Vault — Kürzel-Index")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    breite = pdf.w - pdf.l_margin - pdf.r_margin
    sp_kuerzel = 52
    sp_name = breite - sp_kuerzel

    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 9, "Vault — Kürzel-Index",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(1)

    # Die Namensregel — der Grund, warum es diesen Zettel gibt.
    pdf.set_font("DejaVu", "", 10)
    pdf.set_fill_color(238)
    pdf.multi_cell(breite, 6,
                   "Dokument:  [KUERZEL] Thema\n"
                   "Sprachnotiz:  [KUERZEL] NOTIZ Thema",
                   fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(3)

    def gruppenkopf(name, anzahl, fortsetzung=False):
        pdf.set_font("DejaVu", "B", 13)
        titel = f"{name} ({anzahl})" + (" — Fortsetzung" if fortsetzung else "")
        pdf.cell(0, 8, titel, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_draw_color(0)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + breite, pdf.get_y())
        pdf.ln(1.5)

    for name, eintraege in gruppen:
        if not eintraege:
            continue
        if pdf.get_y() > pdf.page_break_trigger - 30:
            pdf.add_page()
        gruppenkopf(name, len(eintraege))
        for kuerzel, ordner in eintraege:
            pdf.set_font("DejaVu", "", 10)
            zeilen = pdf.multi_cell(sp_name, 5.5, ordner, align="L",
                                    dry_run=True, output="LINES")
            hoehe = max(1, len(zeilen)) * 5.5
            if pdf.get_y() + hoehe > pdf.page_break_trigger:
                pdf.add_page()
                gruppenkopf(name, len(eintraege), fortsetzung=True)
            x0, y0 = pdf.l_margin, pdf.get_y()
            pdf.set_font("DejaVu", "B", 10)
            pdf.cell(sp_kuerzel, hoehe, kuerzel)
            pdf.set_xy(x0 + sp_kuerzel, y0)
            pdf.set_font("DejaVu", "", 10)
            pdf.multi_cell(sp_name, 5.5, ordner, align="L",
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_xy(x0, y0 + hoehe)
            pdf.set_draw_color(210)
            pdf.line(x0, pdf.get_y(), x0 + breite, pdf.get_y())
            pdf.set_y(pdf.get_y() + 0.8)
        pdf.ln(4)

    pdf.output(str(ziel_pfad))
    return gesamt


# --------------------------------------------------------------------------
# Graph — Bibliothek aufloesen und hochladen
# --------------------------------------------------------------------------

def bibliothek_aus_antwort(antwort):
    """Die Bibliothek aus einer /sites/{id}/lists-Antwort ziehen.

    Verglichen werden Anzeige-UND interner Name: SharePoint streicht beim
    Anlegen von Hand den Bindestrich aus dem URL-Segment — gemessen 2026-08-16,
    die Bibliothek traegt displayName 'an-remarkable', aber name 'anremarkable'.
    Der Anzeigename ist der Vertrag aus der Doku, der interne bleibt als
    Rueckfalllinie.

    Fehlt sie, ist das VORUEBERGEHEND — anders als beim Abholer (dort ist die
    fehlende Bibliothek ein Konfigurationsbruch einer laufenden Strecke): Hier ist
    die Anlage von Hand der geplante Weg (`Sites.Selected` kann kein
    Schema). Der Job vertagt sich, bis die Bibliothek da ist, und der naechste
    Lauf danach heilt ohne Zutun."""
    liste = next((l for l in antwort.get("value", [])
                  if BIBLIOTHEK in ((l.get("displayName") or "").lower(),
                                    (l.get("name") or "").lower())), None)
    if not liste:
        raise Fehler(VORUEBERGEHEND,
                     f"Bibliothek '{BIBLIOTHEK}' gibt es auf der Site noch nicht — "
                     f"sie entsteht von Hand. Vertagt bis zum Lauf danach.")
    return liste["id"]


def bibliothek_aufloesen(token):
    """(site_id, drive_id) der Ziel-Bibliothek."""
    site = geheimnis("m365.env", "M365_SITE_ID")
    if not site:
        raise Fehler(DAUERHAFT, "M365_SITE_ID fehlt in m365.env.")
    antwort, _ = graph_mit_kopf(token, "GET",
                                f"/sites/{site}/lists?$select=id,name,displayName")
    list_id = bibliothek_aus_antwort(antwort)
    drive, _ = graph_mit_kopf(token, "GET",
                              f"/sites/{site}/lists/{list_id}/drive?$select=id")
    return site, drive["id"]


def hochladen(token, drive_id, name, inhalt):
    """PUT auf denselben Pfad ersetzt — genau das ist hier gewollt: ein stabiler
    Name, jeder Lauf legt die aktuelle Fassung darueber. Danach wird die Groesse
    zurueckgelesen: erst der Nachweis macht den Upload zum Ergebnis."""
    req = urllib.request.Request(
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/"
        f"{urllib.parse.quote(name)}:/content",
        data=inhalt, method="PUT",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/pdf"})
    try:
        with urllib.request.urlopen(req, timeout=120) as antwort:
            element = json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        raise Fehler(VORUEBERGEHEND, f"Upload '{name}' -> HTTP {fehler.code}.") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"Upload nicht moeglich ({fehler}).") from fehler
    ist, _ = graph_mit_kopf(token, "GET",
                            f"/drives/{drive_id}/items/{element['id']}?$select=size,webUrl")
    if ist.get("size") != len(inhalt):
        raise Fehler(VORUEBERGEHEND,
                     f"Upload unvollstaendig: {ist.get('size')} statt "
                     f"{len(inhalt)} Bytes in der Bibliothek.")
    return ist.get("webUrl", "")


def schreibprobe(token, drive_id):
    """Die Pflicht-Probe vor dem Cron-Eintrag: hochladen, lesen, loeschen.

    Geloescht wird NUR die eigene Testdatei, ueber die Kennung aus dem eigenen
    Upload — nie ueber einen Namen, der jemand anderem gehoeren koennte."""
    name = "_schreibprobe.txt"
    inhalt = f"Schreibprobe remarkable-index {datetime.datetime.now().isoformat()}".encode()
    req = urllib.request.Request(
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/"
        f"{urllib.parse.quote(name)}:/content",
        data=inhalt, method="PUT",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "text/plain"})
    with urllib.request.urlopen(req, timeout=60) as antwort:
        element = json.loads(antwort.read())
    print(f"  hochgeladen: {name} ({len(inhalt)} Bytes)")

    ist, _ = graph_mit_kopf(token, "GET",
                            f"/drives/{drive_id}/items/{element['id']}?$select=size")
    if ist.get("size") != len(inhalt):
        raise Fehler(DAUERHAFT, f"gelesen: {ist.get('size')} Bytes — stimmt nicht.")
    print(f"  gelesen: Groesse stimmt ({ist['size']} Bytes)")

    req = urllib.request.Request(
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{element['id']}",
        method="DELETE",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60):
        pass
    print("  geloescht: Testdatei ist wieder weg")
    print("SCHREIBPROBE BESTANDEN — hochladen, lesen, loeschen.")


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trockenlauf", action="store_true", help="nichts hochladen")
    ap.add_argument("--ausgabe", help="PDF nur lokal schreiben, kein Graph")
    ap.add_argument("--pruefe-zugang", action="store_true")
    ap.add_argument("--schreibprobe", action="store_true",
                    help="Testdatei hochladen, lesen, loeschen")
    a = ap.parse_args()

    try:
        if a.pruefe_zugang:
            _, drive_id = bibliothek_aufloesen(graph_token())
            print(f"Bibliothek '{BIBLIOTHEK}': erreichbar (Drive {drive_id[:8]}…).")
            return 0

        if a.schreibprobe:
            _, drive_id = bibliothek_aufloesen(graph_token())
            schreibprobe(graph_token(), drive_id)
            return 0

        vault = vault_wurzel()
        register, kollisionen = lade_register(vault)
        if not register:
            raise Fehler(DAUERHAFT,
                         "Register ist leer — kein Kuerzel in den Baeumen. "
                         "Das waere ein leerer Index, der wird nicht hochgeladen.")
        for k, a1, a2 in kollisionen:
            print(f"WARNUNG: Kuerzel '{k}' doppelt: {a1} UND {a2} — "
                  f"der Index zeigt {a1}.", file=sys.stderr)

        gruppen = gruppieren(register)
        for name, eintraege in gruppen:
            print(f"  {name}: {len(eintraege)} Kuerzel")

        if a.ausgabe:
            gesamt = pdf_bauen(gruppen, a.ausgabe)
            print(f"PDF geschrieben: {a.ausgabe} ({gesamt} Kuerzel).")
            return 0

        if not a.trockenlauf:
            # Bibliothek VOR dem Rendern aufloesen: vertagen heisst nichts tun,
            # nicht erst ein PDF bauen und es dann wegwerfen.
            token = graph_token()
            _, drive_id = bibliothek_aufloesen(token)

        with tempfile.TemporaryDirectory() as tmp:
            pfad = Path(tmp) / "index.pdf"
            gesamt = pdf_bauen(gruppen, pfad)
            inhalt = pfad.read_bytes()
        print(f"PDF erzeugt: {gesamt} Kuerzel, {len(inhalt) // 1024} KB.")

        if a.trockenlauf:
            print("Trockenlauf — nichts hochgeladen.")
            return 0

        url = hochladen(token, drive_id, DATEINAME, inhalt)
        print(f"Hochgeladen als '{DATEINAME}' — Groesse in der Bibliothek "
              f"nachgelesen, stimmt.\n  {url}")
        return 0

    except Fehler as fehler:
        wort = "VERTAGT" if fehler.klasse == VORUEBERGEHEND else "ABBRUCH"
        print(f"{wort}: {fehler}", file=sys.stderr)
        return fehler.rc


if __name__ == "__main__":
    sys.exit(main())
