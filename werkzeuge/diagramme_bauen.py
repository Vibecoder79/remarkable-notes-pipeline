#!/usr/bin/env python3
"""Erzeugt die Diagramme der Doku — als .excalidraw UND als .svg.

Warum ein Generator und nicht zwei Dateien von Hand
---------------------------------------------------
Excalidraw ist bearbeitbar, rendert aber auf GitHub nicht: Ein Leser sieht dort rohes
JSON. SVG rendert ueberall und laesst sich nicht sinnvoll von Hand nachziehen.

Beide von Hand zu pflegen hiesse, zwei Fassungen desselben Bildes zu haben — und die
zweite altert ab der ersten Aenderung, ohne dass es auffaellt. Dieselbe Ueberlegung
wie bei «Zeiger statt Inhalt» (E-01), nur fuer Zeichnungen.

Wer ein Diagramm aendert, aendert die Beschreibung unten und laesst neu erzeugen.
Die .excalidraw-Datei bleibt trotzdem von Hand bearbeitbar — sie ist dann nur nicht
mehr die Quelle.

Aufruf:
    diagramme_bauen.py [ziel-verzeichnis]
"""
import json
import sys
from pathlib import Path

# Farben. Bewusst wenige und mit Bedeutung, nicht zur Zierde:
FARBEN = {
    "quelle":  ("#1971c2", "#d0ebff"),   # blau  — was von aussen kommt
    "job":     ("#2f9e44", "#d3f9d8"),   # gruen — was der Code tut
    "speicher":("#f08c00", "#ffec99"),   # gelb  — wo etwas liegt
    "gefahr":  ("#e03131", "#ffe3e3"),   # rot   — Abweisung, Fehler
    "neutral": ("#1e1e1e", "#f8f9fa"),
}
SCHRIFT = 16
ZEILE = 20


class Bild:
    def __init__(self, titel):
        self.titel = titel
        self.el = []
        self.n = 0

    def _id(self, p="e"):
        self.n += 1
        return f"{p}{self.n}"

    def kasten(self, x, y, b, h, text, art="neutral", rund=True):
        strich, fuell = FARBEN[art]
        kid = self._id("k")
        tid = self._id("t")
        self.el.append({
            "id": kid, "type": "rectangle", "x": x, "y": y, "width": b, "height": h,
            "angle": 0, "strokeColor": strich, "backgroundColor": fuell,
            "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
            "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "roundness": {"type": 3} if rund else None,
            "seed": 1000 + self.n, "version": 1, "versionNonce": 1000 + self.n,
            "isDeleted": False, "boundElements": [{"id": tid, "type": "text"}],
            "updated": 1, "link": None, "locked": False,
        })
        zeilen = text.split("\n")
        self.el.append({
            "id": tid, "type": "text", "x": x + 8, "y": y + (h - len(zeilen) * ZEILE) / 2,
            "width": b - 16, "height": len(zeilen) * ZEILE, "angle": 0,
            "strokeColor": strich, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
            "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "roundness": None, "seed": 2000 + self.n, "version": 1,
            "versionNonce": 2000 + self.n, "isDeleted": False, "boundElements": [],
            "updated": 1, "link": None, "locked": False, "text": text,
            "fontSize": SCHRIFT, "fontFamily": 1, "textAlign": "center",
            "verticalAlign": "middle", "containerId": kid, "originalText": text,
            "autoResize": True, "lineHeight": 1.25,
        })
        return {"x": x, "y": y, "b": b, "h": h, "text": text, "art": art}

    def text(self, x, y, text, art="neutral", groesse=13, ausrichtung="left"):
        strich, _ = FARBEN[art]
        zeilen = text.split("\n")
        self.el.append({
            "id": self._id("f"), "type": "text", "x": x, "y": y,
            "width": max(len(z) for z in zeilen) * groesse * 0.55,
            "height": len(zeilen) * groesse * 1.25, "angle": 0,
            "strokeColor": strich, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid",
            "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "roundness": None, "seed": 3000 + self.n, "version": 1,
            "versionNonce": 3000 + self.n, "isDeleted": False, "boundElements": [],
            "updated": 1, "link": None, "locked": False, "text": text,
            "fontSize": groesse, "fontFamily": 1, "textAlign": ausrichtung,
            "verticalAlign": "top", "containerId": None, "originalText": text,
            "autoResize": True, "lineHeight": 1.25,
        })
        return {"x": x, "y": y, "text": text, "groesse": groesse, "art": art,
                "ausrichtung": ausrichtung}

    def pfeil(self, x1, y1, x2, y2, beschriftung="", art="neutral"):
        strich, _ = FARBEN[art]
        self.el.append({
            "id": self._id("p"), "type": "arrow", "x": x1, "y": y1,
            "width": abs(x2 - x1), "height": abs(y2 - y1), "angle": 0,
            "strokeColor": strich, "backgroundColor": "transparent",
            "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": "solid",
            "roughness": 1, "opacity": 100, "groupIds": [], "frameId": None,
            "roundness": {"type": 2}, "seed": 4000 + self.n, "version": 1,
            "versionNonce": 4000 + self.n, "isDeleted": False, "boundElements": [],
            "updated": 1, "link": None, "locked": False,
            "points": [[0, 0], [x2 - x1, y2 - y1]], "lastCommittedPoint": None,
            "startBinding": None, "endBinding": None,
            "startArrowhead": None, "endArrowhead": "arrow", "elbowed": False,
        })
        if beschriftung:
            self.text((x1 + x2) / 2 - len(beschriftung) * 3.2,
                      (y1 + y2) / 2 - 18, beschriftung, art, 12)
        return {"x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "beschriftung": beschriftung, "art": art}


def excalidraw(bild):
    return json.dumps({
        "type": "excalidraw", "version": 2,
        "source": "https://github.com/ — diagramme_bauen.py",
        "elements": bild.el,
        "appState": {"gridSize": None, "viewBackgroundColor": "#ffffff"},
        "files": {},
    }, ensure_ascii=False, indent=2)


def svg(bild):
    """SVG aus denselben Elementen. Bewusst schlicht — es soll lesbar sein, nicht
    wie eine Handzeichnung aussehen."""
    xs = [e["x"] for e in bild.el] + [e["x"] + e.get("width", 0) for e in bild.el]
    ys = [e["y"] for e in bild.el] + [e["y"] + e.get("height", 0) for e in bild.el]
    for e in bild.el:
        if e["type"] == "arrow":
            for px, py in e["points"]:
                xs.append(e["x"] + px)
                ys.append(e["y"] + py)
    minx, maxx = min(xs) - 24, max(xs) + 24
    miny, maxy = min(ys) - 24, max(ys) + 24
    b, h = maxx - minx, maxy - miny

    def esc(s):
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    teile = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{minx} {miny} {b} {h}" '
        f'width="{b}" height="{h}" font-family="ui-sans-serif, system-ui, sans-serif">',
        '<defs><marker id="spitze" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-end">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="context-stroke"/></marker></defs>',
        f'<rect x="{minx}" y="{miny}" width="{b}" height="{h}" fill="#ffffff"/>',
    ]
    for e in bild.el:
        if e["type"] == "rectangle":
            teile.append(
                f'<rect x="{e["x"]}" y="{e["y"]}" width="{e["width"]}" '
                f'height="{e["height"]}" rx="8" fill="{e["backgroundColor"]}" '
                f'stroke="{e["strokeColor"]}" stroke-width="2"/>')
        elif e["type"] == "arrow":
            (x1, y1), (x2, y2) = e["points"][0], e["points"][-1]
            teile.append(
                f'<line x1="{e["x"] + x1}" y1="{e["y"] + y1}" x2="{e["x"] + x2}" '
                f'y2="{e["y"] + y2}" stroke="{e["strokeColor"]}" stroke-width="2" '
                f'marker-end="url(#spitze)"/>')
    for e in bild.el:
        if e["type"] != "text":
            continue
        zeilen = e["text"].split("\n")
        anker = {"center": "middle", "left": "start", "right": "end"}[e["textAlign"]]
        x = e["x"] + (e["width"] / 2 if e["textAlign"] == "center" else 0)
        for i, z in enumerate(zeilen):
            y = e["y"] + e["fontSize"] * (0.95 + i * 1.25)
            teile.append(
                f'<text x="{x:.0f}" y="{y:.0f}" fill="{e["strokeColor"]}" '
                f'font-size="{e["fontSize"]}" text-anchor="{anker}" '
                f'{"font-weight=\"600\"" if e["containerId"] else ""}>{esc(z)}</text>')
    teile.append("</svg>")
    return "\n".join(teile)


# ---------------------------------------------------------------------------
# Die Diagramme
# ---------------------------------------------------------------------------

def strecke_gesamt():
    b = Bild("Die Strecke vom Tablet ins Vault")
    b.text(40, 20, "Vom Tablet ins Vault — der Hinweg", "neutral", 22)
    b.text(40, 50, "Alle 15 Minuten. Deterministisch, ohne Sprachmodell.", "neutral", 13)

    b.kasten(40, 120, 200, 80, "Tablet\n[ACME] Zonenskizze", "quelle")
    b.kasten(360, 120, 210, 80, "Dienstpostfach\ntablet@example.com", "speicher")
    b.kasten(690, 120, 200, 80, "Abholer\nDMARC-Gate", "job")
    b.kasten(1010, 120, 220, 80, "Bibliothek\nStatus = Neu", "speicher")

    b.pfeil(245, 160, 355, 160, "Mail + PDF")
    b.pfeil(575, 160, 685, 160, "alle 15 Min")
    b.pfeil(895, 160, 1005, 160, "Upload")

    b.kasten(1010, 260, 220, 70, "abgewiesen\ngezählt, nie still weg", "gefahr")
    b.pfeil(800, 205, 1010, 268, "DMARC scheitert", "gefahr")

    b.kasten(1010, 410, 220, 80, "Zuordner\nKürzel auflösen", "job")
    b.pfeil(1120, 335, 1120, 405)

    b.kasten(640, 410, 260, 80, "Ohne Zuordnung\nwartet sichtbar", "gefahr")
    b.pfeil(1005, 450, 905, 450, "kein Kürzel", "gefahr")
    b.pfeil(770, 405, 1060, 335, "umbenennen", "job")

    b.kasten(1010, 570, 220, 90, "Zeiger-Notiz\nim Projekt\n+ Textauszug", "speicher")
    b.pfeil(1120, 495, 1120, 565, "eindeutig")

    b.kasten(640, 570, 260, 90, "Projekt-Hub\nzeigt sie per Abfrage", "speicher")
    b.pfeil(1005, 615, 905, 615)

    b.text(40, 420,
           "Das PDF bleibt in der\nBibliothek. Ins Vault\nkommt ein Zeiger,\nkein Inhalt.  (E-01)",
           "neutral", 14)
    b.text(40, 560,
           "Der Kreis über\n«Ohne Zuordnung»\nist die Selbstheilung:\nnichts geht verloren.",
           "neutral", 14)
    return b


def kuerzel_routing():
    b = Bild("Das Kürzel-Routing")
    b.text(40, 20, "Wie ein Kürzel zum Ordner wird", "neutral", 22)
    b.text(40, 50, "Zeichenvergleich, kein Verstehen. Es wird nie geraten.  (E-08)",
           "neutral", 13)

    b.kasten(40, 100, 340, 70, "2026-08-15 [ACME] Zonenskizze.pdf", "quelle")
    b.text(40, 185, "Datum weg, Endung weg  →  «[ACME] Zonenskizze»", "neutral", 13)

    b.kasten(40, 230, 340, 60, "Kürzel = ACME", "job")
    b.pfeil(210, 175, 210, 225)

    b.kasten(40, 350, 340, 80, "Register\nbei jedem Lauf aus dem Vault gebaut", "job")
    b.pfeil(210, 295, 210, 345)

    b.text(470, 340, "gelesen aus fünf Bäumen:", "neutral", 14)
    baeume = [
        ("02 Projekte", "kein Präfix", "ACME"),
        ("09 Vertrieb", "VTR-", "VTR-ACME"),
        ("10 Personen", "P-", "P-MUSTER-M"),
        ("04 Ressourcen/Persönliche Notizen", "PN-", "PN-LERNEN"),
        ("03 Bereiche", "kein Präfix", "BEREICH-A"),
    ]
    y = 375
    for name, praefix, beispiel in baeume:
        b.kasten(470, y, 420, 46, f"{name}   ·   {praefix}   ·   z.B. {beispiel}",
                 "speicher")
        y += 56
    b.pfeil(385, 390, 465, 400)

    b.kasten(40, 500, 340, 90,
             "Ziel: 02 Projekte/Acme/\nNotizen/", "speicher")
    b.pfeil(210, 435, 210, 495)

    b.text(40, 700,
           "Kein Kürzel · unbekannt · mehrdeutig · klein geschrieben · nicht am Anfang\n"
           "→  keine Zuordnung. Das Dokument wartet sichtbar, statt falsch zu landen.",
           "gefahr", 14)
    return b


def m365_architektur():
    b = Bild("Die Microsoft-365-Architektur")
    b.text(40, 20, "Zwei App-Registrierungen, zwei Grenzen", "neutral", 22)
    b.text(40, 50,
           "Ein Schlüssel für alles wäre einfacher — und gäbe dem Abholer Senderecht "
           "auf jedes Postfach.  (E-09)", "neutral", 13)

    b.kasten(40, 110, 300, 100,
             "App «tablet-abholer»\nMail.ReadWrite + Mail.Send", "job")
    b.kasten(40, 250, 300, 90,
             "Application Access Policy\nRestrictAccess", "gefahr")
    b.pfeil(190, 215, 190, 245)

    b.kasten(40, 380, 300, 80,
             "Sicherheitsgruppe\nein Mitglied", "speicher")
    b.pfeil(190, 345, 190, 375)

    b.kasten(40, 500, 300, 80,
             "Dienstpostfach\ntablet@example.com", "speicher")
    b.pfeil(190, 465, 190, 495)

    b.kasten(480, 110, 300, 100,
             "App «notizen-plattform»\nSites.Selected", "job")
    b.kasten(480, 250, 300, 90,
             "Grant je Site\nPOST /sites/{id}/permissions", "gefahr")
    b.pfeil(630, 215, 630, 245)

    b.kasten(480, 380, 300, 80, "SharePoint-Site", "speicher")
    b.pfeil(630, 345, 630, 375)

    b.kasten(480, 500, 145, 80, "remarkable\n(Hinweg)", "speicher")
    b.kasten(635, 500, 145, 80, "an-remarkable\n(Rückweg)", "speicher")
    b.pfeil(600, 465, 550, 495)
    b.pfeil(660, 465, 700, 495)

    b.text(850, 120,
           "Gemessen, in beide Richtungen:\n\n"
           "Postfach-App  →  Dienstpostfach      200\n"
           "Postfach-App  →  anderes Postfach    403\n"
           "Bibliotheks-App → Dienstpostfach     403\n\n"
           "Die Eingrenzung ist gemessen,\nnicht geglaubt.", "neutral", 14)
    b.text(850, 300,
           "Sites.Selected allein\ngewährt NICHTS.\nOhne den Grant je Site\nantwortet alles mit 403 —\n"
           "und es gibt keine\nOberfläche dafür.", "gefahr", 14)
    b.text(850, 450,
           "Die Policy greift in\nStunden, nicht Minuten.\nGemessen: rund fünf.\n"
           "Solange blockt sie auch\ndas erlaubte Postfach.\nNicht schrauben — warten.", "gefahr", 14)
    return b


def sprachnotiz_leiter():
    b = Bild("Der eine Modellaufruf")
    b.text(40, 20, "Die Leiter: wann überhaupt ein Modell?", "neutral", 22)
    b.text(40, 50,
           "Die einzige Stelle der Strecke mit Sprachmodell — und auch dort erst ab "
           "zwei Kandidaten.  (E-07)", "neutral", 13)

    b.kasten(40, 110, 300, 70, "Sprachnotiz\n[ACME] NOTIZ Thema", "quelle")
    b.kasten(40, 220, 300, 70,
             "Zeichnungen im selben\nNotizen/-Ordner zählen", "job")
    b.pfeil(190, 185, 190, 215)

    b.kasten(40, 340, 300, 60, "0 Kandidaten → nichts", "neutral")
    b.kasten(40, 420, 300, 60, "1 Kandidat → verknüpfen", "job")
    b.kasten(40, 500, 300, 60, "2+ → Modell fragen", "gefahr")
    b.pfeil(190, 295, 130, 335)
    b.pfeil(190, 295, 190, 415)
    b.pfeil(190, 295, 250, 495)

    b.text(420, 100, "Die vier Verteidigungen", "neutral", 18)
    v = [
        ("1  Index statt Pfad",
         "Das Modell gibt eine ZAHL in eine\nmaschinell gebaute Liste zurück.\n"
         "Kein Pfad. Ein Satz im Transkript\nkann keinen Schreibort wählen."),
        ("2  Belegpflicht",
         "Es nennt den Satz wörtlich, der zur\nWahl führte. Das Programm prüft, ob\n"
         "er dort steht. Kein Beleg, keine\nVerknüpfung — zeigen statt assoziieren."),
        ("3  Fremdtext im Zaun",
         "Transkript zwischen Marken, mit dem\nSatz: alles darin ist Material,\n"
         "nie Auftrag. Senkt die Rate,\ngarantiert nichts — deshalb 1."),
        ("4  Schreiben eng",
         "Nur EINE Wikilink-Zeile an zwei\nbenannte Dateien, idempotent.\n"
         "Kein Anlegen, Verschieben, Löschen."),
    ]
    y = 140
    for titel, text in v:
        b.kasten(420, y, 380, 46, titel, "job")
        b.text(430, y + 54, text, "neutral", 13)
        y += 150
    return b


def fehlerklassen():
    b = Bild("Fehlerklassen und Idempotenz")
    b.text(40, 20, "Zwei Fehlerklassen — und die Reihenfolge", "neutral", 22)
    b.text(40, 50,
           "Die Klasse entscheidet über die Reaktion, nicht der Fehlertext.  (E-03)",
           "neutral", 13)

    b.kasten(40, 110, 380, 110,
             "VORÜBERGEHEND     rc 69\nNetz weg · 5xx · Drosselung\n→ nichts tun, nächster Lauf holt es",
             "job")
    b.kasten(40, 250, 380, 110,
             "DAUERHAFT     rc 77\n401 · 403 · 404 · Fehlkonfiguration\n→ erneut hilft NIE, sofort melden",
             "gefahr")
    b.text(40, 380,
           "Ein Job, der beides gleich behandelt,\nist entweder laut oder blind.",
           "neutral", 14)

    b.text(520, 100, "Die Reihenfolge ist die Idempotenz", "neutral", 18)
    schritte = [
        "1  prüfen      DMARC-Gate",
        "2  kappen      Rumpf auf 4'000 Zeichen",
        "3  hochladen   Datei + ALLE Spalten in einem Zug",
        "4  wegräumen   Mail verschieben — erst jetzt",
    ]
    y = 140
    for s in schritte:
        b.kasten(520, y, 460, 50, s, "speicher")
        if y < 290:
            b.pfeil(750, y + 50, 750, y + 62)
        y += 62
    b.text(520, 400,
           "Bricht der Lauf zwischen 3 und 4 ab,\n"
           "wiederholt der nächste — statt zu verlieren.\n\n"
           "Umgekehrt wäre die Mail weg\nund das Dokument nicht da.", "neutral", 14)
    b.text(520, 500,
           "Namensgleichheit ist kein Beweis für Identität:\n"
           "gleicher Name + gleicher Eingang  →  ersetzen\n"
           "gleicher Name + anderer Eingang   →  zweites Dokument",
           "gefahr", 14)
    return b


def main():
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/diagramme")
    ziel.mkdir(parents=True, exist_ok=True)
    for name, bauen in [
        ("strecke-gesamt", strecke_gesamt),
        ("kuerzel-routing", kuerzel_routing),
        ("m365-architektur", m365_architektur),
        ("sprachnotiz-leiter", sprachnotiz_leiter),
        ("fehlerklassen", fehlerklassen),
    ]:
        bild = bauen()
        (ziel / f"{name}.excalidraw").write_text(excalidraw(bild), encoding="utf-8")
        (ziel / f"{name}.svg").write_text(svg(bild), encoding="utf-8")
        print(f"{name}: {len(bild.el)} Elemente → .excalidraw + .svg")
    return 0


if __name__ == "__main__":
    sys.exit(main())
