#!/usr/bin/env python3
"""Gemeinsamer Unterbau aller Programme dieser Strecke: Geheimnisse, Graph, Fehlerklassen.

Warum es dieses Modul gibt
--------------------------
Die Programme der Strecke teilen sich vier Fragen: Woher kommt ein Geheimnis? Wie
sieht ein Graph-Aufruf aus? Welche Fehler darf man wiederholen? Wo liegt das Vault?
Dieselbe Antwort fuenfmal zu schreiben hiesse, sie fuenfmal unterschiedlich falsch
zu haben.

Die zwei Fehlerklassen — der wichtigste Gedanke hier
----------------------------------------------------
Ohne diese Unterscheidung laeuft ein Konfigurationsfehler endlos im Kreis:

    VORUEBERGEHEND Netz weg, 5xx, Drosselung, Zeitueberschreitung
                    -> nichts tun. Der naechste Lauf holt es nach. Selbstheilend.
    DAUERHAFT 401, 403, 404, falsch konfigurierte Bibliothek
                    -> erneut versuchen hilft NIE. Sofort melden.

Ein Job, der beides gleich behandelt, ist entweder laut (er meldet jeden Netzhaenger)
oder blind (er verschluckt einen falschen Schluessel). Die Klasse entscheidet ueber
die Reaktion, nicht der Fehlertext.

Was hier NICHT hineingehoert
----------------------------
Alles, was nur ein einziges Programm braucht. Dieses Modul ist der Unterbau, nicht
die Abstellkammer — sobald eine Funktion nur von einer Stelle gerufen wird, gehoert
sie dorthin.
"""
import http.client
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HIER = Path(__file__).resolve().parent

# --- Rueckgabewerte, damit ein Aufrufer die Klasse ohne Textlesen erkennt ----
# Die Zahlen folgen sysexits.h. Ein Cron-Wrapper kann daran entscheiden, ob er
# meldet oder schweigt, ohne die Ausgabe zu lesen.
RC_OK = 0
RC_VORUEBERGEHEND = 69 # EX_UNAVAILABLE — erneut versuchen ist richtig
RC_DAUERHAFT = 77 # EX_NOPERM — erneut versuchen hilft nie
RC_KONFIG = 78 # EX_CONFIG — es fehlt etwas, das jemand hinlegen muss

VORUEBERGEHEND = "voruebergehend"
DAUERHAFT = "dauerhaft"

GRAPH = "https://graph.microsoft.com/v1.0"


class Fehler(Exception):
    """Ein Fehler mit Klasse. Die Klasse entscheidet ueber die Reaktion, nicht der Text."""

    def __init__(self, klasse: str, text: str):
        super().__init__(text)
        self.klasse = klasse
        self.text = text

    @property
    def rc(self) -> int:
        return RC_VORUEBERGEHEND if self.klasse == VORUEBERGEHEND else RC_DAUERHAFT


# --- Orte -------------------------------------------------------------------

# Die Datei, an der eine Vault-Wurzel erkannt wird. Frei waehlbar — was zaehlt, ist
# dass sie im Wurzelverzeichnis liegt und sonst nirgends. Im Ursprungsbetrieb ist es
# die Regeldatei des Vaults; wer keine hat, legt eine leere `.vault`-Datei an.
#
# Geprueft wird auf ZWEI Merkmale (Marker UND ein erwarteter Ordner), nicht auf blosse
# Existenz des Verzeichnisses: Ein leerer oder falscher Pfad waere sonst eine gueltige
# Wurzel, und die Programme schrieben ihre Notizen ins Nichts.
VAULT_MARKER = os.environ.get("VAULT_MARKER", "CLAUDE.md")
VAULT_BAUM = os.environ.get("VAULT_BAUM", "02 Projekte")


def vault_wurzel() -> Path:
    """Wo das Vault liegt — fester Pfad mit Override, keine Ableitung aus `__file__`.

    Die Ableitung aus dem eigenen Ort waere nur so lange richtig, wie der Code IM
    Vault liegt. Sobald er ein eigenes Repo bekommt, zeigt sie ins Leere. `VAULT_DIR`
    bleibt als Override, damit ein Test nicht den echten Bestand anfasst.

    Geprueft wird auf zwei Merkmale, nicht auf blosse Existenz: ein leeres oder
    falsches Verzeichnis waere sonst eine gueltige Wurzel, und die Programme schrieben
    ihre Notizen ins Nichts.
    """
    wurzel = Path(os.environ.get("VAULT_DIR", "/opt/vault"))
    if not (wurzel / VAULT_MARKER).is_file() or not (wurzel / VAULT_BAUM).is_dir():
        raise Fehler(DAUERHAFT,
                     f"'{wurzel}' ist keine Vault-Wurzel: erwartet werden die Datei "
                     f"'{VAULT_MARKER}' und der Ordner '{VAULT_BAUM}'. "
                     f"Beide Namen sind ueber VAULT_MARKER / VAULT_BAUM einstellbar.")
    return wurzel


def geheimnis(datei: str, schluessel: str) -> str | None:
    """Einen Wert aus einer Umgebungsdatei lesen — zeilenweise, nie per `source`.

    Zuerst gilt die echte Umgebungsvariable: so laesst sich ein Job testen, ohne die
    Datei anzufassen.

    Zeilenweise und nicht `source`, weil die Datei eine WERTETABELLE ist und kein
    Programm. Ein `source` fuehrte beliebigen Shell-Code aus, den jemand dort ablegt
    — bei einer Datei, die per Definition Geheimnisse traegt, ist das die falsche
    Voreinstellung.

    Der WERT wird nirgends ausgegeben, auch nicht im Fehlerfall. Gemeldet wird nur,
    OB er da ist.
    """
    aus_umgebung = os.environ.get(schluessel)
    if aus_umgebung:
        return aus_umgebung
    pfad = Path(os.environ.get("SECRETS_DIR", "/etc/notizen-strecke")) / datei
    try:
        for zeile in pfad.read_text(encoding="utf-8").splitlines():
            treffer = re.match(rf"^{re.escape(schluessel)}=(.*)$", zeile.strip())
            if treffer:
                wert = treffer.group(1).strip().strip('"').strip("'")
                return wert or None
    except OSError:
        return None
    return None


# --- Frontmatter ------------------------------------------------------------

def frontmatter(text: str) -> dict[str, str]:
    """Die flachen Felder aus dem YAML-Kopf. Bewusst kein YAML-Parser.

    Gebraucht werden Zeichenketten wie `meeting_key` und `typ` — dafuer eine
    Abhaengigkeit einzufuehren waere teurer als diese zwoelf Zeilen. Verschachtelte
    Strukturen liefert die Funktion NICHT; wer sie braucht, nimmt einen Parser.
    """
    if not text.startswith("---"):
        return {}
    ende = text.find("\n---", 3)
    if ende == -1:
        return {}
    felder: dict[str, str] = {}
    for zeile in text[3:ende].split("\n"):
        treffer = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", zeile)
        if treffer:
            felder[treffer.group(1)] = treffer.group(2).strip().strip('"').strip("'")
    return felder


def frontmatter_setzen(pfad: Path, felder: dict[str, str]) -> None:
    """Felder fortschreiben, ohne den Rumpf anzufassen.

    Geschrieben wird ueber eine Nebendatei und `os.replace`. Ein halb geschriebenes
    Frontmatter waere ein Zustand, den kein Lauf mehr einordnen kann — und `os.replace`
    ist auf demselben Dateisystem atomar.
    """
    text = pfad.read_text(encoding="utf-8")
    if not text.startswith("---"):
        raise Fehler(DAUERHAFT, f"'{pfad.name}' hat kein Frontmatter.")
    ende = text.find("\n---", 3)
    if ende == -1:
        raise Fehler(DAUERHAFT, f"'{pfad.name}' hat kein abgeschlossenes Frontmatter.")

    kopf = text[3:ende].split("\n")
    rest = text[ende + 4:]
    offen = dict(felder)
    neu: list[str] = []
    for zeile in kopf:
        treffer = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*)$", zeile)
        if treffer and treffer.group(1) in offen:
            neu.append(f"{treffer.group(1)}: {offen.pop(treffer.group(1))}")
        else:
            neu.append(zeile)
    for schluessel, wert in offen.items():
        neu.append(f"{schluessel}: {wert}")

    neben = pfad.with_suffix(pfad.suffix + ".neu")
    neben.write_text("---" + "\n".join(neu) + "\n---" + rest, encoding="utf-8")
    os.replace(neben, pfad)


# --- Microsoft Graph --------------------------------------------------------

def token_holen(datei: str, praefix: str) -> str:
    """Client-Credentials-Fluss fuer EINE App-Registrierung.

    `datei` ist die Umgebungsdatei, `praefix` der Namensteil der Schluessel — so
    bedient dieselbe Funktion beide Registrierungen der Strecke:

        token_holen("m365.env", "M365")              Bibliothek (Sites.Selected)
        token_holen("remarkable.env", "REMARKABLE")  Tablet-Postfach (Mail.*)
        token_holen("postfach.env", "NOTIZEN")       Mail-Eingang (Mail.*)

    Zwei Registrierungen sind kein Zufall, sondern die Architektur — siehe
    `docs/entscheidungen/E-09 Zwei App-Registrierungen.md`. Ein Schluessel fuer alles
    haette dem Postfach-Zugang Rechte gegeben, die er nie braucht.

    Kein Nutzer im Spiel: der Job laeuft ohne Menschen davor.
    """
    pflicht = (f"{praefix}_TENANT_ID", f"{praefix}_CLIENT_ID", f"{praefix}_CLIENT_SECRET")
    werte, fehlend = {}, []
    for schluessel in pflicht:
        wert = geheimnis(datei, schluessel)
        if wert:
            werte[schluessel] = wert
        else:
            fehlend.append(schluessel)
    if fehlend:
        raise Fehler(DAUERHAFT,
                     f"Zugang unvollstaendig — fehlt: {', '.join(fehlend)}.\n"
                     f" Erwartet in $SECRETS_DIR/{datei}.")
    daten = urllib.parse.urlencode({
        "client_id": werte[f"{praefix}_CLIENT_ID"],
        "client_secret": werte[f"{praefix}_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()
    adresse = (f"https://login.microsoftonline.com/{werte[f'{praefix}_TENANT_ID']}"
               f"/oauth2/v2.0/token")
    try:
        with urllib.request.urlopen(urllib.request.Request(adresse, data=daten),
                                    timeout=30) as antwort:
            d = json.loads(antwort.read().decode())
    except urllib.error.HTTPError as fehler:
        # 400/401 hier heisst falsche Zugangsdaten. Erneut versuchen hilft nie.
        # Der Rumpf wird NICHT ausgegeben — er kann den gesendeten Wert spiegeln.
        raise Fehler(DAUERHAFT,
                     f"Anmeldung abgelehnt ({fehler.code}) fuer {praefix}.") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"Anmeldung nicht erreichbar ({fehler}).") from fehler
    token = d.get("access_token")
    if not token:
        raise Fehler(DAUERHAFT, f"Kein access_token fuer {praefix}.")
    return token


def graph_token() -> str:
    """Token der Bibliotheks-App — die im Alltag haeufigste der beiden."""
    return token_holen("m365.env", "M365")


def graph_mit_kopf(token: str, methode: str, pfad: str, rumpf: dict | None = None,
                   zusatz: dict[str, str] | None = None) -> tuple[dict, dict[str, str]]:
    """Wie `graph()`, gibt aber zusaetzlich die Antwort-Kopfzeilen zurueck.

    Warum es das braucht: Manche Graph-Aufrufe antworten mit **202 Accepted und
    leerem Rumpf**, und die Kennung des angelegten Objekts steht ausschliesslich in
    der Kopfzeile `Location`. Wer nur den Rumpf liest, hat etwas angelegt und weiss
    nicht was — und der naechste Lauf legt es ein zweites Mal an. Dieselbe Klasse
    Fehler wie bei `graph_alle()`: eine Antwort, die vollstaendig aussieht und es
    nicht ist.

    Die Kopfzeilen kommen kleingeschrieben zurueck. HTTP-Kopfzeilen sind
    gross-/kleinschreibungsunabhaengig, und Graph schreibt sie nicht stabil gleich.
    """
    daten = json.dumps(rumpf, ensure_ascii=False).encode() if rumpf is not None else None
    kopf = {"Authorization": f"Bearer {token}"}
    if daten is not None:
        kopf["Content-Type"] = "application/json"
    if zusatz:
        kopf.update(zusatz)
    bitte = urllib.request.Request(pfad if pfad.startswith("http") else GRAPH + pfad,
                                   data=daten, headers=kopf, method=methode)
    try:
        with urllib.request.urlopen(bitte, timeout=60) as antwort:
            roh = antwort.read().decode()
            kopfzeilen = {k.lower(): v for k, v in antwort.headers.items()}
    except urllib.error.HTTPError as fehler:
        rumpf_text = fehler.read().decode(errors="replace")[:400]
        if fehler.code in (400, 401, 403, 404):
            raise Fehler(DAUERHAFT,
                         f"Graph {methode} {pfad} -> {fehler.code}: {rumpf_text}") from fehler
        raise Fehler(VORUEBERGEHEND,
                     f"Graph {methode} {pfad} -> {fehler.code}") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"Graph nicht erreichbar ({fehler}).") from fehler
    except http.client.InvalidURL as fehler:
        # Eine unbaubare Adresse ist ein Programmfehler, kein Netzproblem — erneut
        # versuchen hilft nie. Sie entsteht, wenn ein Wert in den Pfad geraet, der
        # dort nicht hingehoert: ein Leerzeichen, ein Gedankenstrich, ein Umlaut aus
        # einem Anzeigenamen. Ohne diesen Zweig endet der Lauf mit einer
        # Python-Rueckverfolgung — und die hat keine Fehlerklasse, der Aufrufer weiss
        # also nicht, ob er wiederholen darf.
        raise Fehler(DAUERHAFT,
                     f"Graph {methode}: die Adresse laesst sich nicht bauen "
                     f"({fehler}). Ein Wert im Pfad ist nicht kodiert.") from fehler
    return (json.loads(roh) if roh.strip() else {}), kopfzeilen


def graph(token: str, methode: str, pfad: str, rumpf: dict | None = None,
          zusatz: dict[str, str] | None = None) -> dict:
    """Ein Graph-Aufruf. Fehler bekommen ihre Klasse hier, nicht beim Aufrufer."""
    return graph_mit_kopf(token, methode, pfad, rumpf, zusatz)[0]


def graph_binaer(token: str, methode: str, pfad: str, daten: bytes,
                 zusatz: dict[str, str] | None = None) -> dict:
    """Rohe Bytes an Graph schicken — Dateiinhalte, Upload-Broecken.

    Getrennt von `graph()`, weil sich die beiden im Rumpf widersprechen: dort ist er
    ein Woerterbuch und wird zu JSON, hier ist er bereits der Inhalt. Ein gemeinsamer
    Parameter, der mal das eine und mal das andere bedeutet, waere die Sorte
    Zweideutigkeit, die man erst im Fehlerfall bemerkt.
    """
    kopf = {"Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream"}
    if zusatz:
        kopf.update(zusatz)
    bitte = urllib.request.Request(pfad if pfad.startswith("http") else GRAPH + pfad,
                                   data=daten, headers=kopf, method=methode)
    try:
        with urllib.request.urlopen(bitte, timeout=300) as antwort:
            roh = antwort.read().decode(errors="replace")
    except urllib.error.HTTPError as fehler:
        text = fehler.read().decode(errors="replace")[:400]
        klasse = DAUERHAFT if fehler.code in (400, 401, 403, 404) else VORUEBERGEHEND
        raise Fehler(klasse,
                     f"Graph {methode} {pfad[:80]} -> {fehler.code}: {text}") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"Graph nicht erreichbar ({fehler}).") from fehler
    return json.loads(roh) if roh.strip() else {}


def graph_alle(token: str, pfad: str, grenze: int = 5000) -> list[dict]:
    """Eine Graph-Sammlung VOLLSTAENDIG holen, ueber alle Seiten.

    Graph blaettert. `$top` ist eine Bitte, keine Zusage — die Antwort traegt dann
    `@odata.nextLink`, und wer den ignoriert, bekommt einen Ausschnitt, der aussieht
    wie das Ganze. Gemessen an einer Liste mit 35 Zeilen:

        $top=5 -> 5 Zeilen, nextLink: JA
        $top=500 -> 35 Zeilen, nextLink: nein

    Der zweite Fall ist der Alltag, und deshalb faellt es lange nicht auf. Der erste
    zeigt, was oberhalb der Seitengrenze passiert — und dort haengt Schlimmeres dran
    als eine unvollstaendige Anzeige: Idempotenz-Pruefungen lesen diese Listen, um zu
    sehen, ob ein Eintrag schon vorliegt. Faellt eine Zeile hinter die Seitengrenze,
    gilt sie als nicht vorhanden und wird ein zweites Mal angelegt. Das ist keine
    Fehlermeldung, das ist eine Dublette.

    `grenze` ist kein Kuerzen, sondern eine Notbremse gegen eine Endlosschleife. Wird
    sie erreicht, gibt es einen DAUERHAFT-Fehler und keine gekuerzte Liste: eine zu
    kurze Antwort waere genau das stille Verhalten, das diese Funktion abstellt.
    """
    gesammelt: list[dict] = []
    naechste: str | None = pfad
    while naechste:
        antwort = graph(token, "GET", naechste)
        gesammelt.extend(antwort.get("value", []))
        if len(gesammelt) > grenze:
            raise Fehler(DAUERHAFT,
                         f"Mehr als {grenze} Eintraege in '{pfad}'. Entweder ist die "
                         f"Liste ausser Kontrolle geraten, oder Graph blaettert im "
                         f"Kreis. Nicht gekuerzt weitergegeben — pruefen.")
        naechste = antwort.get("@odata.nextLink")
    return gesammelt


# Wie lange auf eine Drosselung gewartet wird, bevor aufgegeben wird.
GEDULD_S = (15, 30, 60, 120, 240)


def mit_geduld(was: str, arbeit):
    """Einen Aufruf wiederholen, solange sein Fehler VORUEBERGEHEND ist.

    SharePoint drosselt bei Massenarbeit die BIBLIOTHEK, nicht den einzelnen Aufruf:
    nach einigen Dutzend Schreibvorgaengen kommt 429, kurz darauf schon beim blossen
    GET. `graph()` stuft 429 richtig ein, wiederholt aber nicht — fuer einen Job, der
    hundertfach schreibt, ist das zu wenig, und «erneut starten» wuerde zur
    Bedienungsanleitung statt zur Ausnahme.

    DAUERHAFTE Fehler fliegen sofort weiter. Ein 403 wird durch Warten nicht besser,
    und wer ihn fuenfmal wiederholt, verschleiert ihn nur.
    """
    for versuch, pause in enumerate((*GEDULD_S, None), 1):
        try:
            return arbeit()
        except Fehler as fehler:
            if fehler.klasse != VORUEBERGEHEND or pause is None:
                raise
            print(f" … {was}: {fehler.text[:60]} — warte {pause}s "
                  f"(Versuch {versuch} von {len(GEDULD_S) + 1})")
            time.sleep(pause)


# --- Der administrative Meldeweg -------------------------------------------

def melden(text: str) -> bool:
    """Den administrativen Kanal benutzen. Betrieb, nicht Inhalt.

    INHALTE gehen hier nicht durch — keine Notiztitel, keine Entscheidungen. Was
    hinausgeht, sind Kennungen und Fehlerlagen. Der Aufrufer haelt sich daran; diese
    Funktion prueft es nicht, weil sie es nicht kann.

    Schlaegt die Zustellung fehl, ist das eine WARNUNG und kein Abbruch: Der Job hat
    seine Arbeit getan, nur die Meldung kam nicht an. Wer hier abbraeche, machte aus
    einem stummen Melder einen kaputten Job.
    """
    melder = HIER / "melder.sh"
    if not melder.is_file() or not os.access(melder, os.X_OK):
        print(f"WARNUNG: '{melder}' fehlt — die Meldung bleibt im Log stehen:\n{text}",
              file=sys.stderr)
        return False
    lauf = subprocess.run([str(melder), text], capture_output=True, text=True)
    if lauf.returncode != 0:
        print(f"WARNUNG: Meldung nicht zugestellt (rc={lauf.returncode}): "
              f"{lauf.stderr.strip()[:300]}", file=sys.stderr)
        return False
    return True
