#!/usr/bin/env python3
"""Holt reMarkable-Post aus dem Postfach und legt die PDFs in die Bibliothek.

Grundlage: E-01 reMarkable-Anbindung §2 und §5. Deterministisch,
kein Sprachmodell, kein Vault-Zugriff — ins Vault schreibt erst der Zuordner
.

Vier Aufgaben, in dieser Reihenfolge je Mail:
  1. pruefen    DMARC-Gate: `Authentication-Results` muss `dmarc=pass` tragen
                UND die geprüfte Domain muss zum From passen (Alignment).
                Was scheitert, wandert nach `abgewiesen` — nie still verwerfen.
  2. kappen     Mailrumpf an der Trennlinie `--` abschneiden und laengenbegrenzen.
  3. hochladen  Anhang als `YYYY-MM-DD <Name>.pdf` in die Bibliothek, im selben
                Zug die Spalten Eingang, Status=Neu und Kontext setzen.
  4. wegraeumen Mail nach `verarbeitet` — ERST nach erfolgreichem Upload samt
                Spalten. Diese Reihenfolge ist die Idempotenz: bricht der Lauf
                dazwischen ab, wiederholt der naechste, statt zu verlieren.

Zwei Zugaenge, bewusst getrennt:
  * Postfach:   eigene App `sb-remarkable-abholer` (remarkable.env), per
                Application Access Policy auf genau dieses eine Postfach begrenzt.
  * Bibliothek: die Plattform-App (m365.env) mit `Sites.Selected` auf der Site
                «Automation» — dieselbe, die die Freigabestrecke nutzt.

Aufrufe:
    remarkable_abholer.py --pruefe-zugang
    remarkable_abholer.py --trockenlauf
    remarkable_abholer.py
"""
import argparse
import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

from graph_basis import (DAUERHAFT, VORUEBERGEHEND, Fehler, geheimnis,
                                graph_mit_kopf, graph_token)

# Absender, die das Gate passieren duerfen. Belegt am 2026-07-30: das Tablet
# schickt als `my=remarkable.com@share.remarkable.com` im Auftrag von
# `my@remarkable.com` — beide Domains gehoeren dem Hersteller.
ERLAUBTE_DOMAINS = ("remarkable.com", "share.remarkable.com")

# Kappungsgrenze fuer den Rumpftext. Die SharePoint-Spalte truege 63'999 Zeichen
# (nachgeschlagen 2026-08-15) — die Grenze hier ist bewusst viel enger,
# weil der Text spaeter in Vault-Notizen und Modell-Eingaben landet,
# beides Orte, an denen ungebremster Fremdtext schadet.
KONTEXT_MAX = 4000

# Exchange nimmt rund 25 MB je Anhang an; was groesser ankaeme, waere schon an
# der Mail gescheitert. Die Grenze hier faengt den Rest — als FEHLER, nicht still.
ANHANG_MAX = 25 * 1024 * 1024

BIBLIOTHEK = "remarkable"

# Interne Spaltennamen der Bibliothek, gemessen am 2026-08-15.
# `Vault-Notiz` ist eine TEXTSPALTE: Graph kann Hyperlink-Spalten nicht
# beschreiben (v1.0-Luecke, empirisch bestaetigt) — wer hier eine Link-Spalte
# einplant, baut eine Spalte, die kein Job fuellen kann.
SPALTE_EINGANG = "Eingang"
SPALTE_STATUS = "Status"
SPALTE_KONTEXT = "Kontext"


def postfach():
    return geheimnis("remarkable.env", "REMARKABLE_POSTFACH") or "tablet@example.com"


def mail_token():
    """Client-Credentials-Fluss der dedizierten Postfach-App.

    Bewusst NICHT die Plattform-App: deren Access Policy haelt sie von diesem
    Postfach fern, und die dedizierte App kommt umgekehrt an kein anderes."""
    pflicht = ("REMARKABLE_TENANT_ID", "REMARKABLE_CLIENT_ID", "REMARKABLE_CLIENT_SECRET")
    werte, fehlend = {}, []
    for schluessel in pflicht:
        wert = geheimnis("remarkable.env", schluessel)
        (werte.__setitem__(schluessel, wert) if wert else fehlend.append(schluessel))
    if fehlend:
        raise Fehler(DAUERHAFT,
                     "reMarkable-Zugang unvollstaendig — fehlt: " + ", ".join(fehlend) + ".\n"
                     "  Erwartet in /etc/notizen-strecke/remarkable.env (jobs:vault 0640).")
    daten = urllib.parse.urlencode({
        "client_id": werte["REMARKABLE_CLIENT_ID"],
        "client_secret": werte["REMARKABLE_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()
    adresse = (f"https://login.microsoftonline.com/{werte['REMARKABLE_TENANT_ID']}"
               f"/oauth2/v2.0/token")
    try:
        with urllib.request.urlopen(urllib.request.Request(adresse, data=daten),
                                    timeout=30) as antwort:
            d = json.loads(antwort.read().decode())
    except urllib.error.HTTPError as fehler:
        raise Fehler(DAUERHAFT,
                     f"Anmeldung der Postfach-App abgelehnt ({fehler.code}).") from fehler
    except (urllib.error.URLError, TimeoutError, OSError) as fehler:
        raise Fehler(VORUEBERGEHEND, f"M365-Anmeldung nicht erreichbar ({fehler}).") from fehler
    token = d.get("access_token")
    if not token:
        raise Fehler(DAUERHAFT, "M365 liefert kein access_token fuer die Postfach-App.")
    return token


# --------------------------------------------------------------------------
# Das Mail-Gate — reine Funktionen, damit die Probe sie ohne Tenant messen kann
# --------------------------------------------------------------------------

def kopfwert(kopfzeilen, name):
    """Alle Werte einer Kopfzeile, zusammengefuegt. Graph liefert
    `internetMessageHeaders` als Liste von {name, value}; mehrfach vorkommende
    Zeilen (Authentication-Results je Pruefstation) werden verbunden."""
    name = name.lower()
    werte = [k.get("value", "") for k in (kopfzeilen or [])
             if (k.get("name") or "").lower() == name]
    return "; ".join(werte)


def dmarc_verdikt(kopfzeilen, absender):
    """Das Gate. (True, grund) heisst verarbeiten, (False, grund) heisst abweisen.

    Drei Stufen, jede fuer sich notwendig:
      1. Die Absender-Domain muss eine der erlaubten sein — sonst braucht es
         keinen Blick in die Kopfzeilen.
      2. `Authentication-Results` muss `dmarc=pass` sagen. Der `From`-String
         allein ist unbeglaubigter Text und von jedem setzbar.
      3. Alignment: die Domain, FUER die DMARC bestanden wurde (`header.from=`),
         muss zur Absender-Domain passen. Ein `dmarc=pass` fuer eine fremde
         Domain ist kein Beleg fuer diesen Absender.
    """
    domain = (absender or "").rsplit("@", 1)[-1].strip().lower()
    if domain not in ERLAUBTE_DOMAINS:
        return False, f"Absender-Domain '{domain or 'leer'}' ist nicht erlaubt"

    auth = kopfwert(kopfzeilen, "Authentication-Results").lower()
    if not auth:
        return False, "keine Authentication-Results-Kopfzeile — Echtheit unbelegt"

    dmarc = re.search(r"dmarc=(\w+)", auth)
    if not dmarc:
        return False, "Authentication-Results ohne dmarc-Ergebnis"
    if dmarc.group(1) != "pass":
        return False, f"dmarc={dmarc.group(1)}"

    ausgerichtet = re.search(r"header\.from=([a-z0-9.-]+)", auth)
    if not ausgerichtet:
        return False, "dmarc=pass, aber ohne header.from — Alignment unbelegt"
    hf = ausgerichtet.group(1).strip(".")
    if not (domain == hf or domain.endswith("." + hf) or hf.endswith("." + domain)):
        return False, f"Alignment verletzt: From '{domain}', geprueft wurde '{hf}'"

    return True, f"dmarc=pass fuer {hf}"


def rumpf_kappen(text, grenze=KONTEXT_MAX):
    """Kontext aus dem Mailrumpf: an der Trennlinie schneiden, dann begrenzen.

    Unter `--` stehen «Von meinem reMarkable Paper Tablet gesendet» und der
    Nicht-Antworten-Hinweis — ohne Schnitt stuende das in jeder Notiz. Der
    Herstellersatz selbst ist die Rueckfalllinie, falls die Trennlinie fehlt."""
    zeilen = []
    for zeile in (text or "").replace("\r\n", "\n").split("\n"):
        blank = zeile.strip()
        if blank == "--" or blank.startswith("-- ") or \
                blank.startswith("Von meinem reMarkable"):
            break
        zeilen.append(zeile.rstrip())
    ergebnis = "\n".join(zeilen).strip()
    ergebnis = re.sub(r"\n{3,}", "\n\n", ergebnis)
    if len(ergebnis) > grenze:
        ergebnis = ergebnis[:grenze].rstrip() + " …[gekappt]"
    return ergebnis


def sichere_dateiname(s, max_len=120):
    """SharePoint-vertraeglicher Name. Verbotene Zeichen raus, Laenge begrenzt,
    fuehrende und schliessende Punkte weg (SharePoint lehnt beides ab)."""
    s = re.sub(r'[\\/:*?"<>|#%&{}~]', "-", s or "").strip()
    s = re.sub(r"\s+", " ", s).strip(". ")
    return s[:max_len].rstrip(". ") or "Ohne Namen"


def ziel_name(anhang_name, empfangen_iso, zusatz=""):
    """`YYYY-MM-DD [KUERZEL] Thema.pdf` — das Datum verhindert, dass zwei
    gleichnamige Dokumente verschiedener Tage kollidieren; `zusatz` traegt die
    Uhrzeit nach, wenn dasselbe Thema am selben Tag zweimal kommt."""
    stamm, punkt, endung = (anhang_name or "").rpartition(".")
    if not punkt:
        stamm, endung = anhang_name or "", "pdf"
    datum = (empfangen_iso or "")[:10] or "0000-00-00"
    kern = sichere_dateiname(stamm)
    return f"{datum} {kern}{zusatz}.{endung.lower()}"


# --------------------------------------------------------------------------
# Graph-Zugriffe
# --------------------------------------------------------------------------

def ordner_kennungen(token, pf, anlegen=True):
    """IDs der Unterordner `verarbeitet` und `abgewiesen`. Fehlt einer, wird er
    angelegt — die Ordner sind Teil der Einrichtung, aber ein Abholer,
    der an einem geloeschten Ordner scheitert, waere die schlechtere Antwort."""
    r, _ = graph_mit_kopf(token, "GET",
                          f"/users/{pf}/mailFolders?$select=id,displayName&$top=50")
    vorhanden = {f["displayName"]: f["id"] for f in r.get("value", [])}
    kennungen = {}
    for name in ("verarbeitet", "abgewiesen"):
        if name in vorhanden:
            kennungen[name] = vorhanden[name]
        elif anlegen:
            neu, _ = graph_mit_kopf(token, "POST", f"/users/{pf}/mailFolders",
                                    rumpf={"displayName": name})
            kennungen[name] = neu["id"]
            print(f"  Ordner '{name}' fehlte und wurde angelegt.")
        else:
            kennungen[name] = None
    return kennungen


def bibliothek_aufloesen(site_token):
    """(site_id, list_id, drive_id) der Bibliothek. Aufgeloest je Lauf — die
    Kennungen sind stabil, aber eine Kopie hier waere eine zweite Wahrheit."""
    site = geheimnis("m365.env", "M365_SITE_ID")
    if not site:
        raise Fehler(DAUERHAFT, "M365_SITE_ID fehlt in m365.env.")
    r, _ = graph_mit_kopf(site_token, "GET", f"/sites/{site}/lists?$select=id,name")
    liste = next((l for l in r.get("value", [])
                  if (l.get("name") or "").lower() == BIBLIOTHEK), None)
    if not liste:
        raise Fehler(DAUERHAFT,
                     f"Bibliothek '{BIBLIOTHEK}' nicht auf der Site gefunden — "
                     f"Einrichtung der Bibliothek pruefen.")
    r, _ = graph_mit_kopf(site_token, "GET", f"/sites/{site}/lists/{liste['id']}/drive?$select=id")
    return site, liste["id"], r["id"]


def vorhandener_eingang(site_token, site, list_id, drive_id, name):
    """Traegt die Bibliothek schon eine Datei dieses Namens, und mit welchem
    `Eingang`? None heisst: Name ist frei."""
    try:
        r, _ = graph_mit_kopf(site_token, "GET",
                              f"/drives/{drive_id}/root:/{urllib.parse.quote(name)}:/listItem?$expand=fields($select={SPALTE_EINGANG})")
        return (r.get("fields") or {}).get(SPALTE_EINGANG) or ""
    except Fehler as fehler:
        if "404" in str(fehler):
            return None
        raise


def freier_name(site_token, site, list_id, drive_id, anhang_name, empfangen_iso):
    """Namensgleichheit ist kein Beweis fuer Identitaet (dieselbe Lehre wie beim
    Transkript-Abholer): gleicher Name mit gleichem `Eingang` ist ein Wiederholungslauf
    derselben Mail — ueberschreiben ist dann richtig. Gleicher Name mit anderem
    `Eingang` ist ein ANDERES Dokument — die Uhrzeit kommt in den Namen."""
    uhr = re.sub(r"[^0-9]", "", (empfangen_iso or "")[11:16])
    for zusatz in ("", f" {uhr}" if uhr else " 2", f" {uhr}{re.sub(r'[^0-9]', '', (empfangen_iso or '')[17:19])}"):
        name = ziel_name(anhang_name, empfangen_iso, zusatz)
        bisher = vorhandener_eingang(site_token, site, list_id, drive_id, name)
        if bisher is None or bisher[:19] == (empfangen_iso or "")[:19]:
            return name
    raise Fehler(DAUERHAFT,
                 f"Kein freier Name fuer '{anhang_name}' ({empfangen_iso}) — "
                 f"drei Kandidaten belegt, das ist kein Zufall mehr.")


def hochladen(site_token, site, list_id, drive_id, name, inhalt, empfangen_iso, kontext):
    """Datei plus Spalten in EINEM Zug — danach haengt nichts mehr an der Mail.
    PUT auf denselben Pfad ersetzt; zusammen mit `freier_name()` ist das die
    Wiederholbarkeit nach einem Abbruch zwischen Upload und Wegraeumen."""
    req = urllib.request.Request(
        f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{urllib.parse.quote(name)}:/content",
        data=inhalt, method="PUT",
        headers={"Authorization": f"Bearer {site_token}",
                 "Content-Type": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=300) as antwort:
            element = json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        raise Fehler(VORUEBERGEHEND,
                     f"Upload '{name}' -> HTTP {fehler.code}.") from fehler
    item, _ = graph_mit_kopf(site_token, "GET",
                             f"/drives/{drive_id}/items/{element['id']}/listItem?$select=id")
    graph_mit_kopf(site_token, "PATCH",
                   f"/sites/{site}/lists/{list_id}/items/{item['id']}/fields",
                   rumpf={SPALTE_EINGANG: empfangen_iso,
                          SPALTE_STATUS: "Neu",
                          SPALTE_KONTEXT: kontext})
    return element.get("webUrl", "")


def verschieben(token, pf, mail_id, ordner_id):
    graph_mit_kopf(token, "POST", f"/users/{pf}/messages/{mail_id}/move",
                   rumpf={"destinationId": ordner_id})


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pruefe-zugang", action="store_true")
    ap.add_argument("--trockenlauf", action="store_true", help="nichts schreiben")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    pf = postfach()

    try:
        mt = mail_token()
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2

    if a.pruefe_zugang:
        try:
            r, _ = graph_mit_kopf(mt, "GET",
                                  f"/users/{pf}/mailFolders/inbox/messages?$select=id&$top=1")
            print(f"Postfach {pf}: erreichbar.")
            st = graph_token()
            site, list_id, drive_id = bibliothek_aufloesen(st)
            print(f"Bibliothek '{BIBLIOTHEK}': erreichbar (Liste {list_id[:8]}…).")
            return 0
        except Fehler as fehler:
            print(f"ZUGANG GESTOERT: {fehler}", file=sys.stderr)
            return 2

    try:
        kennungen = ordner_kennungen(mt, pf, anlegen=not a.trockenlauf)
        r, _ = graph_mit_kopf(
            mt, "GET",
            f"/users/{pf}/mailFolders/inbox/messages"
            f"?$select=id,subject,receivedDateTime&$orderby=receivedDateTime&$top={a.limit}")
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2
    mails = r.get("value", [])
    print(f"{len(mails)} Mail(s) im Eingang von {pf}.")
    if not mails:
        return 0

    st = graph_token()
    site, list_id, drive_id = bibliothek_aufloesen(st)

    zaehler = {"verarbeitet": 0, "abgewiesen": 0, "ohne_anhang": 0, "fehler": 0}

    for kopf in mails:
        mid = kopf["id"]
        try:
            m, _ = graph_mit_kopf(
                mt, "GET",
                f"/users/{pf}/messages/{mid}"
                f"?$select=subject,from,receivedDateTime,hasAttachments,body,internetMessageHeaders",
                zusatz={"Prefer": 'outlook.body-content-type="text"'})
        except Fehler as fehler:
            print(f"  [FEHLER ] Mail nicht lesbar: {fehler}", file=sys.stderr)
            zaehler["fehler"] += 1
            continue

        absender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
        betreff = (m.get("subject") or "")[:60]
        empfangen = m.get("receivedDateTime") or ""

        ok, grund = dmarc_verdikt(m.get("internetMessageHeaders"), absender)
        if not ok:
            print(f"  [ABGEWIESEN] {empfangen[:16]} {absender} — {grund}")
            if not a.trockenlauf:
                verschieben(mt, pf, mid, kennungen["abgewiesen"])
            zaehler["abgewiesen"] += 1
            continue

        try:
            anh, _ = graph_mit_kopf(mt, "GET", f"/users/{pf}/messages/{mid}/attachments")
        except Fehler as fehler:
            print(f"  [FEHLER ] Anhaenge nicht lesbar ({betreff}): {fehler}", file=sys.stderr)
            zaehler["fehler"] += 1
            continue
        dateien = [x for x in anh.get("value", [])
                   if x.get("@odata.type") == "#microsoft.graph.fileAttachment"
                   and not x.get("isInline")]

        if not dateien:
            print(f"  [OHNE ANHANG] {empfangen[:16]} {betreff} — nichts hochzuladen")
            if not a.trockenlauf:
                verschieben(mt, pf, mid, kennungen["verarbeitet"])
            zaehler["ohne_anhang"] += 1
            continue

        kontext = rumpf_kappen(((m.get("body") or {}).get("content")) or "")
        mail_gescheitert = False

        for datei in dateien:
            groesse = datei.get("size") or 0
            if groesse > ANHANG_MAX:
                print(f"  [FEHLER ] '{datei.get('name')}' ist {groesse // (1024*1024)} MB — "
                      f"ueber der Grenze. Mail bleibt im Eingang.", file=sys.stderr)
                zaehler["fehler"] += 1
                mail_gescheitert = True
                continue
            try:
                name = freier_name(st, site, list_id, drive_id,
                                   datei.get("name") or "dokument.pdf", empfangen)
                if a.trockenlauf:
                    print(f"  [TROCKEN] wuerde hochladen: {name} "
                          f"(Kontext {len(kontext)} Zeichen)")
                    continue
                inhalt = base64.b64decode(datei.get("contentBytes") or "")
                hochladen(st, site, list_id, drive_id, name, inhalt, empfangen, kontext)
                print(f"  [BIBLIOTHEK] {name} ({groesse // 1024} KB, "
                      f"Kontext {len(kontext)} Zeichen)")
            except Fehler as fehler:
                print(f"  [FEHLER ] {datei.get('name')}: {fehler}", file=sys.stderr)
                zaehler["fehler"] += 1
                mail_gescheitert = True

        if mail_gescheitert or a.trockenlauf:
            continue
        verschieben(mt, pf, mid, kennungen["verarbeitet"])
        zaehler["verarbeitet"] += 1

    print(f"\nVerarbeitet: {zaehler['verarbeitet']}, abgewiesen: {zaehler['abgewiesen']}, "
          f"ohne Anhang: {zaehler['ohne_anhang']}, Fehler: {zaehler['fehler']}.")
    if a.trockenlauf:
        print("Trockenlauf — nichts geschrieben, nichts verschoben.")
    return 1 if zaehler["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
