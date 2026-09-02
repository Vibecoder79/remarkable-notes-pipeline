#!/usr/bin/env python3
"""Holt Notizen aus dem Postfach notizen@example.com und legt sie ueber das Kuerzel im Betreff in Notizen/ ab — mit Marker `Ressource:` als Zeiger auf einen Link.

Grundlage: Eigner-Entscheid, E-04
(Fremdmaterial-Zaun) (`Notizen/` entsteht beim ersten Inhalt). Muster:
`remarkable_abholer.py` (Gate, Idempotenz) und `remarkable_zuordner.py`
(Zuordnung, Notiz, Veroeffentlichung). Deterministisch, kein Sprachmodell,
kein Netz ausser Graph.

Der Use Case in einem Satz: Egal ob eigener Gedanke, Text aus einem ChatGPT-Chat
oder eine weitergeleitete Mail — soll etwas ins Vault, geht es per Mail an
notizen@example.com, immer mit `[KUERZEL] Thema` im Betreff.

Was dieses Programm je Mail tut, in dieser Reihenfolge:
  1. Gate      Die Absenderadresse muss auf der Allowlist stehen
               (NOTIZEN_ABSENDER in postfach.env). Danach zwei
               Zweige, am 27.08.2026 an echten Testmails gemessen:
               - extern (Domain != example.com): `dmarc=pass` UND Alignment
                 `header.from` = Absenderdomain — dasselbe Gate wie beim Tablet.
                 Gmail und GMX bestehen es.
               - intern (Domain == example.com): Exchange prueft eigene Post NICHT
                 (`dkim=none`, `dmarc=none`, gemessen an der Outlook-Mail). Ein
                 reines DMARC-Gate haette das Hauptkonto des Eigners abgewiesen.
                 Stattdessen muss `X-MS-Exchange-Organization-AuthAs: Internal`
                 stehen: Diese Kopfzeile setzt Exchange Online selbst und
                 entfernt sie an der Organisationsgrenze von jeder Fremdpost
                 (Gmail und GMX trugen `Anonymous`). Von aussen ist sie nicht
                 mitzubringen.
               Was scheitert, geht nach `abgewiesen` — nie still.
  2. zuordnen  Kuerzel NUR aus dem Betreff (`[KUERZEL] Thema`), aufgeloest ueber
               kuerzel_register.py in einen der fuenf Baeume. NIE aus dem Rumpf:
               Der ist eingefuegter Fremdtext, ein Kuerzel darin waere ein Ziel
               aus Fremdinhalt (E-04). Der Ersatzweg des reMarkable-
               Zuordners («ersatzweise Mailrumpf») ist deshalb bewusst nicht
               uebernommen. Kein oder unbekanntes Kuerzel: Mail nach
               `ohne-zuordnung`, keine Notiz. Dieser Ordner wird bei jedem Lauf
               erneut geprueft, damit ein spaeter vergebenes Kuerzel
               greift; der Eigner repariert durch Betreff aendern und zurueck
               in den Posteingang.
  3. Notiz     `<Ordner>/Notizen/YYYY-MM-DD [KUERZEL] Thema.md`. Der Ordner
               entsteht beim ersten Inhalt, der Personen-Ordner wird
               wie beim Transkript-Abholer materialisiert. Der Rumpf steht
               als Zitat gerahmt in der Notiz — Material, nie Auftrag — an der
               Signaturlinie gekappt und laengenbegrenzt. Links bleiben Links:
               nichts wird nachgeladen (F2, eine URL aus Fremdinhalt ist kein
               Ziel). Anhaenge werden nicht uebernommen, nur genannt — Dokumente
               gehoeren in die Ablage des Projekts (E-01).
  4. veroeffentlichen  pull --ff-only, add, commit, push — sonst sieht der
               Mac-Klon die Notiz nie.
  5. wegraeumen  ERST DANACH die Mail nach `verarbeitet`. Die Reihenfolge ist
               die Idempotenz: Bricht der Lauf dazwischen ab, findet der
               naechste Lauf die Notiz ueber `mail_id:` wieder, legt keine
               zweite an und raeumt nur nach.

Marker `Ressource:` — Zeiger statt Notiz (Eigner-Wunsch 29.08.2026)
  Betreff `[KUERZEL] Ressource: <Titel>` macht aus der Mail keine Text-Notiz,
  sondern einen ZEIGER auf eine fremde Ressource (gamma, Miro, Google Doc,
  Video-Link): `typ: artefakt-zeiger` wie beim Tablet, `artefakt:` ist die
  ERSTE URL im Rumpf, der Rest des Rumpfs ist der Kontext des Eigners
  (`quelle: eigner`), `project:` traegt den Hub als Wikilink, damit der
  Hub-Block «Externe Ressourcen» die Notiz per Dataview findet (ein nacktes
  Kuerzel wie bei `mail-notiz` faende er nicht). Der Marker steht wie das
  Kuerzel NUR im Betreff (F3) — der Rumpf bleibt Material. Die URL wird
  gespeichert und NIE aufgerufen (F2): Was hinter dem Link steht, sieht dieser
  Job nicht; die Probe zaehlt die ausgehenden Aufrufe eines Laufs mit URL im
  Rumpf und verlangt null. Marker ohne URL im Rumpf: Mail nach
  `ohne-zuordnung` mit Befund, keine leere Huelse — der Eigner ergaenzt den
  Link und legt die Mail zurueck. Ohne Marker: alles wie oben (`mail-notiz`).
  Das Marker-Wort steht in MARKER_RESSOURCE: `Ressource`, vom Eigner am
  29.08.2026 bestaetigt — ein anderes Wort waere genau diese eine Zeile.

Zugang: eigene App `sb-vault-abholer` (postfach.env), per
Application Access Policy auf genau dieses Postfach begrenzt — gemessen
27.08.2026: eigenes Postfach 200, Eigner-Postfach 403 (Einrichtung, Schritt 1).

Aufrufe:
    notiz_abholer.py --pruefe-zugang
    notiz_abholer.py --trockenlauf
    notiz_abholer.py
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from graph_basis import (DAUERHAFT, VORUEBERGEHEND, Fehler, geheimnis,
                                graph_mit_kopf)
from vault_baeume import materialisiere_personen_ordner, sichere_dateiname
from kuerzel_register import FRONTMATTER_KEY, KUERZEL_MUSTER, lade_register, ordne_zu
from remarkable_abholer import kopfwert

ENV = "postfach.env"

# Die Domain des eigenen Tenants. Post von hier prueft Exchange nicht per DMARC
# (gemessen 27.08.2026) — fuer sie gilt der interne Zweig des Gates.
EIGENE_DOMAIN = "example.com"

# Kappungsgrenze fuer den Rumpf. Bewusst WEITER als die 4'000 Zeichen des
# Tablet-Kontexts: Dort ist der Rumpf ein Begleitsatz zum PDF, hier IST er der
# Inhalt — ein ChatGPT-Brainstorm hat leicht 10'000 Zeichen. 20'000 sind rund
# fuenf Seiten; was darueber liegt, gehoert als Dokument in die Ablage.
NOTIZ_MAX = 20_000

# Unterordner auf Wurzel-Ebene neben dem Posteingang (bewaehrtes Muster).
ORDNER = ("verarbeitet", "abgewiesen", "ohne-zuordnung")

# Einzeilige Handy-Signaturen, an denen der Rumpf endet — nur bei exakter Zeile,
# damit ein Satz, der zufaellig so beginnt, nicht den Rest abschneidet.
SIGNATUR_ZEILEN = {
    "von meinem iphone gesendet", "sent from my iphone",
    "von meinem ipad gesendet", "sent from my ipad",
    "outlook für ios abrufen", "outlook für android abrufen",
    "get outlook for ios", "get outlook for android",
    "von meinem samsung galaxy smartphone gesendet.",
}

# Marker im Betreff, der aus der Mail einen Zeiger macht:
# `[KUERZEL] Ressource: <Titel>`. Gross/klein egal, Doppelpunkt Pflicht. Das Wort
# hat der Eigner am 29.08.2026 bestaetigt — ein anderes waere genau diese eine Zeile.
MARKER_RESSOURCE = "Ressource"
MARKER_MUSTER = re.compile(rf"^\s*{MARKER_RESSOURCE}\s*:\s*(.*)$", re.I)

# Die erste URL im Rumpf wird `artefakt:` — erkannt, nie aufgerufen (F2).
# Outlook rahmt Links im Textrumpf mit spitzen Klammern (`Titel<https://…>`),
# Menschen haengen Punkt oder Klammer an; beides gehoert nicht zur URL.
URL_MUSTER = re.compile(r"https?://[^\s<>\"'\]]+", re.I)
URL_NACHSATZ = ".,;:!?»›'\""


# --------------------------------------------------------------------------
# Zugaenge
# --------------------------------------------------------------------------

def postfach():
    return geheimnis(ENV, "NOTIZEN_POSTFACH") or "notizen@example.com"


def erlaubte_absender():
    """Die Allowlist, kommagetrennt aus NOTIZEN_ABSENDER. Leer heisst: kein
    Gate moeglich — dann laeuft nichts, statt alles durchzulassen."""
    roh = geheimnis(ENV, "NOTIZEN_ABSENDER") or ""
    adressen = {a.strip().lower() for a in roh.split(",") if a.strip()}
    if not adressen:
        raise Fehler(DAUERHAFT,
                     f"NOTIZEN_ABSENDER fehlt oder ist leer in {ENV} — "
                     f"ohne Allowlist kein Gate, ohne Gate kein Lauf.")
    return adressen


def mail_token():
    """Client-Credentials-Fluss der dedizierten Postfach-App (Muster
    der Einrichtung). Bewusst NICHT die Plattform-App: deren Access Policy haelt sie von
    diesem Postfach fern, und diese App kommt umgekehrt an kein anderes."""
    pflicht = ("NOTIZEN_TENANT_ID", "NOTIZEN_CLIENT_ID", "NOTIZEN_CLIENT_SECRET")
    werte, fehlend = {}, []
    for schluessel in pflicht:
        wert = geheimnis(ENV, schluessel)
        (werte.__setitem__(schluessel, wert) if wert else fehlend.append(schluessel))
    if fehlend:
        raise Fehler(DAUERHAFT,
                     "Postfach-Zugang unvollstaendig — fehlt: " + ", ".join(fehlend) + ".\n"
                     f"  Erwartet in /etc/notizen-strecke/{ENV} (jobs:vault 0640).")
    daten = urllib.parse.urlencode({
        "client_id": werte["NOTIZEN_CLIENT_ID"],
        "client_secret": werte["NOTIZEN_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }).encode()
    adresse = (f"https://login.microsoftonline.com/{werte['NOTIZEN_TENANT_ID']}"
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
# Das Gate — reine Funktionen, damit die Probe sie ohne Tenant messen kann
# --------------------------------------------------------------------------

def _header_from(auth):
    m = re.search(r"header\.from=([a-z0-9.-]+)", auth or "", re.I)
    return m.group(1).lower() if m else ""


def gate_verdikt(kopfzeilen, absender, erlaubte, eigene_domain=EIGENE_DOMAIN):
    """(ok, grund). Erst die Adresse, dann der Zweig.

    Der externe Zweig ist `dmarc_verdikt()` aus remarkable_abholer.py ohne die
    Domainliste — hier ist die Adresse die Liste. Der interne Zweig ist neu und
    steht auf der Messung vom 27.08.2026: Tenant-interne Post traegt
    `dmarc=none`, aber `AuthAs: Internal`, Fremdpost traegt `Anonymous`."""
    adresse = (absender or "").strip().lower()
    if not adresse:
        return False, "kein Absender"
    if adresse not in erlaubte:
        return False, f"Absender '{adresse}' steht nicht auf der Liste"
    domain = adresse.rsplit("@", 1)[-1]
    auth = kopfwert(kopfzeilen, "Authentication-Results")

    if domain == eigene_domain:
        authas = kopfwert(kopfzeilen, "X-MS-Exchange-Organization-AuthAs").strip().lower()
        if authas != "internal":
            return False, f"intern erwartet, AuthAs='{authas or 'leer'}'"
        hf = _header_from(auth)
        if hf != domain:
            return False, (f"intern, aber header.from='{hf or 'leer'}' passt nicht "
                           f"zur Absenderdomain")
        return True, f"intern: AuthAs=Internal, header.from={domain}"

    if not auth:
        return False, "keine Authentication-Results-Kopfzeile"
    dmarc = re.search(r"dmarc=(\w+)", auth)
    if not dmarc:
        return False, "Authentication-Results ohne dmarc-Ergebnis"
    if dmarc.group(1).lower() != "pass":
        return False, f"dmarc={dmarc.group(1)}"
    hf = _header_from(auth)
    if not hf:
        return False, "dmarc=pass, aber ohne header.from — Alignment unbelegt"
    if hf != domain:
        return False, f"Alignment verletzt: From '{domain}', geprueft wurde '{hf}'"
    return True, f"extern: dmarc=pass fuer {domain}"


# --------------------------------------------------------------------------
# Betreff, Rumpf, Notiz — ebenfalls rein
# --------------------------------------------------------------------------

def betreff_zerlegen(betreff):
    """(kuerzel, thema) aus `[KUERZEL] Thema`; (None, None) ohne Klammer-Kuerzel.
    Das Thema ist whitespace-normalisiert — `[PROJ]  Test ` wird `Test`."""
    m = KUERZEL_MUSTER.match(betreff or "")
    if not m:
        return None, None
    return m.group(1), re.sub(r"\s+", " ", m.group(2)).strip()


def zuordnen(betreff, register):
    """(ziel_rel, kuerzel, thema, grund). Ohne Thema wird `Notiz` gesetzt, damit
    ein nackter Betreff `[PER]` nicht an der Thema-Pflicht des Meeting-Parsers
    scheitert — bei Meetings ist das Thema Pflicht, bei einer Notiz nicht."""
    kuerzel, thema = betreff_zerlegen(betreff)
    if not kuerzel:
        return None, None, None, "kein Kuerzel im Betreff (erwartet: '[KUERZEL] Thema')"
    titel = f"[{kuerzel}] {thema or 'Notiz'}"
    ziel_rel, grund = ordne_zu(titel, register)
    return ziel_rel, kuerzel, (thema or "Notiz"), grund


def ressource_erkennen(thema):
    """(ist_ressource, titel). `Ressource: 360-Grad` -> (True, '360-Grad'); ohne
    Marker -> (False, thema). Ein nackter Marker ergibt den Titel `Ressource`,
    damit die Notiz einen Namen hat. Gross/klein egal, kein Synonymraten."""
    m = MARKER_MUSTER.match(thema or "")
    if not m:
        return False, thema
    titel = re.sub(r"\s+", " ", m.group(1)).strip()
    return True, (titel or MARKER_RESSOURCE)


def url_herausloesen(text):
    """(url, rest). Die ERSTE URL im Text wird `artefakt:` — gespeichert, nie
    aufgerufen. `rest` ist der Text ohne diese eine URL (und ohne Outlooks spitze
    Klammern darum); jede weitere URL bleibt als Link im Kontext stehen. Keine
    URL: (None, text) — der Aufrufer macht daraus einen Befund, keine Huelse."""
    m = URL_MUSTER.search(text or "")
    if not m:
        return None, text or ""
    url = m.group(0).rstrip(URL_NACHSATZ)
    # Eine schliessende Klammer gehoert nur dazu, wenn eine oeffnende drin ist
    # (Wikipedia-Links haben sie, ein Satz in Klammern nicht).
    while url.endswith(")") and url.count("(") < url.count(")"):
        url = url[:-1].rstrip(URL_NACHSATZ)
    rest = re.sub(r"<?" + re.escape(url) + r">?", "", text, count=1)
    rest = "\n".join(z.rstrip() for z in rest.split("\n"))
    rest = re.sub(r"\n{3,}", "\n\n", rest).strip()
    return url, rest


def hub_link(vault, ziel_rel, kuerzel):
    """`[[<Hub>]]` fuer `project:` des Zeigers — die Datei im Zielordner, die das
    Kuerzel als `meeting_key`/`lead_key` traegt. Der Hub-Block «Externe
    Ressourcen» filtert auf `project = this.file.link`; ein nacktes Kuerzel
    (wie bei `mail-notiz`) faende er nicht. Gibt es keine Hub-Datei im Ordner
    (Personen-Ordner vor der Materialisierung, Trockenlauf), faellt es auf das
    Kuerzel zurueck — dann zeigt der Ordner-Block die Notiz, der Hub-Block nicht,
    und beides steht so in der Datei."""
    ordner = os.path.join(vault, ziel_rel)
    try:
        namen = sorted(f for f in os.listdir(ordner) if f.endswith(".md"))
    except OSError:
        return kuerzel
    for name in namen:
        try:
            with open(os.path.join(ordner, name), encoding="utf-8") as fh:
                kopf = fh.read(4096)
        except OSError:
            continue
        m = FRONTMATTER_KEY.search(kopf)
        if m and m.group(1) == kuerzel:
            return f"[[{name[:-3]}]]"
    return kuerzel


def rumpf_kappen(text, grenze=NOTIZ_MAX):
    """Rumpf an der Signaturlinie schneiden, dann begrenzen. Geschnitten wird nur
    an `--` und an exakten Handy-Signaturzeilen; alles andere bleibt, denn ein
    zu eifriger Schnitt kostet Eigner-Text, ein fehlender nur eine Signatur."""
    zeilen = []
    for zeile in (text or "").replace("\r\n", "\n").split("\n"):
        blank = zeile.strip()
        if blank == "--" or blank.startswith("-- ") or blank.lower() in SIGNATUR_ZEILEN:
            break
        zeilen.append(zeile.rstrip())
    ergebnis = "\n".join(zeilen).strip()
    ergebnis = re.sub(r"\n{3,}", "\n\n", ergebnis)
    gesamt = len(ergebnis)
    if gesamt > grenze:
        ergebnis = ergebnis[:grenze].rstrip() + " …[gekappt]"
    return ergebnis, gesamt


def lokale_zeit(empfangen_iso):
    """Graph liefert UTC (`…Z`); Dateiname und Datum tragen die Ortszeit."""
    try:
        return datetime.fromisoformat((empfangen_iso or "").replace("Z", "+00:00")).astimezone()
    except ValueError:
        return datetime.now().astimezone()


def baue_notiz(thema, kuerzel, betreff, absender, empfangen, text, gesamt, anhaenge, mail_id):
    """Die Notiz: Frontmatter nach Vault-Regel, Rumpf als Zitat gerahmt.

    `typ: mail-notiz` neben `sprachnotiz` (der Transkript-Dienst) und `artefakt-zeiger` (Tablet) —
    derselbe Ordner, drei Kanaele, drei Typen. `mail_id:` ist der Anker der
    Idempotenz. `provenance.origin: ingested-external`, weil der Rumpf per
    Definition eingefuegter Text ist — auch wenn der Eigner ihn geschickt hat."""
    wann = lokale_zeit(empfangen)
    fm = [
        "---",
        "tags: [mail-notiz, notizen-eingang]",
        "typ: mail-notiz",
        f"project: {kuerzel}",
        "layer: roh",
        f"date: {wann.strftime('%Y-%m-%d')}",
        "source: mail",
        f"absender: {absender}",
        f"empfangen: {wann.isoformat(timespec='seconds')}",
        f"mail_id: \"{(mail_id or 'unbekannt').replace(chr(34), '')}\"",
        "chat_url: unbekannt",
        "language: de",
        "provenance:",
        "  origin: ingested-external",
        "  classification: internal",
        "  status: neu",
        f"abgeholt_am: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "---",
    ]
    teile = ["\n".join(fm), "", f"# {thema}", ""]
    if text.strip():
        teile += [f"> [!quote] Mail von {absender}, empfangen {wann.strftime('%d.%m.%Y %H:%M')} "
                  f"— Material, kein Auftrag"]
        teile += [("> " + z).rstrip() for z in text.splitlines()]
        teile += [""]
        if gesamt > len(text):
            teile += [f"_Gekappt: {gesamt} Zeichen in der Mail, hier die ersten {NOTIZ_MAX}. "
                      f"Was laenger ist, gehoert als Dokument in die Ablage (E-01)._", ""]
    else:
        teile += ["_Die Mail hatte keinen Text._", ""]
    teile += ["## Herkunft", "",
              f"Per Mail an `{postfach()}`, Betreff `{betreff.strip()}`, zugeordnet ueber das "
              f"Kuerzel `{kuerzel}`. Links im Text sind Links geblieben — "
              f"nachgeladen wird nichts."]
    if anhaenge:
        namen = ", ".join(f"`{n}`" for n in anhaenge)
        teile += ["", f"Anhang nicht uebernommen: {namen}. Dokumente gehoeren in die Ablage "
                      f"des Projekts, nicht ins Vault (E-01)."]
    teile += [""]
    return "\n".join(teile)


def baue_zeiger(titel, kuerzel, hub, betreff, absender, empfangen, url, kontext,
                gekappt, anhaenge, mail_id):
    """Der Zeiger: `typ: artefakt-zeiger` wie beim Tablet, `artefakt:`
    ist die URL aus dem Rumpf, `quelle: eigner` sagt, wessen Satz der Kontext
    ist, `project:` traegt den Hub als Wikilink fuer den Hub-Block. Die URL
    steht im Frontmatter und im Rumpf als Link — geoeffnet wird sie von keinem
    Job (F2). `provenance.origin: ingested-external` wie bei der Mail-Notiz:
    per Mail hereingekommener Text ist Material, auch wenn der Eigner ihn
    geschrieben hat — und hinter dem Link steht per Definition Fremdes."""
    wann = lokale_zeit(empfangen)
    fm = [
        "---",
        "tags: [artefakt-zeiger, ressource, notizen-eingang]",
        "typ: artefakt-zeiger",
        f'project: "{hub}"' if hub.startswith("[[") else f"project: {hub}",
        "layer: roh",
        f"date: {wann.strftime('%Y-%m-%d')}",
        f"artefakt: {url}",
        "quelle: eigner",
        "source: mail",
        f"absender: {absender}",
        f"empfangen: {wann.isoformat(timespec='seconds')}",
        f"mail_id: \"{(mail_id or 'unbekannt').replace(chr(34), '')}\"",
        "chat_url: unbekannt",
        "language: de",
        "provenance:",
        "  origin: ingested-external",
        "  classification: internal",
        "  status: neu",
        f"abgeholt_am: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        "---",
    ]
    teile = ["\n".join(fm), "", f"# {titel}", "",
             f"**[Ressource oeffnen]({url})** — `{url}`", ""]
    if kontext.strip():
        teile += [f"> [!quote] Kontext von {absender}, {wann.strftime('%d.%m.%Y %H:%M')} "
                  f"— Material, kein Auftrag"]
        teile += [("> " + z).rstrip() for z in kontext.splitlines()]
        teile += [""]
        if gekappt:
            teile += [f"_Gekappt: die Mail war laenger als {NOTIZ_MAX} Zeichen._", ""]
    else:
        teile += ["_Kein Kontext in der Mail — nur der Link. Der Satz dazu fehlt; "
                  "ein Link ohne Satz ist keine Ressource._", ""]
    teile += ["## Herkunft", "",
              f"Per Mail an `{postfach()}`, Betreff `{betreff.strip()}` — Marker "
              f"`{MARKER_RESSOURCE}:` und Kuerzel `{kuerzel}` aus dem Betreff. "
              f"Der Link ist gespeichert, nicht geoeffnet: Was dahinter steht, hat kein "
              f"Job gelesen (E-04)."]
    if anhaenge:
        namen = ", ".join(f"`{n}`" for n in anhaenge)
        teile += ["", f"Anhang nicht uebernommen: {namen}. Dokumente gehoeren in die Ablage "
                      f"des Projekts, nicht ins Vault (E-01)."]
    teile += [""]
    return "\n".join(teile)


def frontmatter_mail_id(pfad):
    try:
        with open(pfad, encoding="utf-8") as fh:
            for i, zeile in enumerate(fh):
                if i > 40:
                    break
                m = re.match(r'^mail_id:\s*"?([^"\n]*)"?\s*$', zeile)
                if m:
                    return m.group(1).strip()
    except OSError:
        pass
    return None


def freier_pfad(vault, ordner_rel, stamm, mail_id, wann):
    """(pfad_rel, schon_da). Namensgleichheit ist kein Beweis fuer Identitaet:
    Gleicher Name mit gleicher `mail_id` ist ein Wiederholungslauf derselben Mail
    — die Notiz liegt schon. Gleicher Name mit anderer `mail_id` ist eine ANDERE
    Mail — die Uhrzeit kommt in den Namen. Nie ueberschreiben."""
    zusaetze = ["", f" {wann.strftime('%H%M')}", f" {wann.strftime('%H%M%S')}"] + \
               [f" {n}" for n in range(2, 10)]
    for zusatz in zusaetze:
        pfad_rel = os.path.join(ordner_rel, f"{stamm}{zusatz}.md")
        voll = os.path.join(vault, pfad_rel)
        if not os.path.exists(voll):
            return pfad_rel, False
        if mail_id and frontmatter_mail_id(voll) == mail_id:
            return pfad_rel, True
    raise Fehler(DAUERHAFT, f"Kein freier Name fuer '{stamm}' in {ordner_rel}.")


# --------------------------------------------------------------------------
# Graph-Zugriffe
# --------------------------------------------------------------------------

def ordner_kennungen(token, pf, anlegen=True):
    """IDs der drei Unterordner. Fehlt einer, wird er angelegt — die Ordner sind
    Teil der Einrichtung, aber ein Abholer, der an einem geloeschten Ordner
    scheitert, waere die schlechtere Antwort."""
    r, _ = graph_mit_kopf(token, "GET",
                          f"/users/{pf}/mailFolders?$select=id,displayName&$top=50")
    vorhanden = {f["displayName"]: f["id"] for f in r.get("value", [])}
    kennungen = {}
    for name in ORDNER:
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


def mail_koepfe(token, pf, ordner, limit):
    r, _ = graph_mit_kopf(
        token, "GET",
        f"/users/{pf}/mailFolders/{ordner}/messages"
        f"?$select=id,subject,receivedDateTime&$orderby=receivedDateTime&$top={limit}")
    return r.get("value", [])


def mail_lesen(token, pf, mid):
    m, _ = graph_mit_kopf(
        token, "GET",
        f"/users/{pf}/messages/{mid}"
        f"?$select=subject,from,receivedDateTime,hasAttachments,body,"
        f"internetMessageHeaders,internetMessageId",
        zusatz={"Prefer": 'outlook.body-content-type="text"'})
    return m


def anhang_namen(token, pf, mid):
    r, _ = graph_mit_kopf(token, "GET",
                          f"/users/{pf}/messages/{mid}/attachments?$select=name,isInline")
    return [x.get("name") or "ohne Namen" for x in r.get("value", [])
            if x.get("@odata.type") == "#microsoft.graph.fileAttachment" and not x.get("isInline")]


def verschieben(token, pf, mid, ordner_id):
    graph_mit_kopf(token, "POST", f"/users/{pf}/messages/{mid}/move",
                   rumpf={"destinationId": ordner_id})


# --------------------------------------------------------------------------
# Vault
# --------------------------------------------------------------------------

def vault_wurzel():
    return os.environ.get("VAULT_DIR", "/opt/vault")


def veroeffentliche(vault, pfade):
    """Committen und pushen — sonst sieht der Eigner die Notizen nie (Mac-Klon).
    Reihenfolge zwingend: erst ziehen (--ff-only), dann committen, dann schieben.
    Auch ohne neue Dateien wird geschoben, wenn ein frueherer Lauf zwar
    committet, aber nicht geschoben hat — sonst blieben Mails im Eingang haengen."""
    def git(*args):
        return subprocess.run(["git", "-C", vault, *args], capture_output=True, text=True)

    if git("pull", "--ff-only", "origin", "main").returncode != 0:
        print("WARNUNG: pull --ff-only fehlgeschlagen — Arbeitskopie haengt zurueck.",
              file=sys.stderr)
        return 1
    if pfade:
        git("add", "--", *pfade)
        n = len(pfade)
        kopf = f"chore(notizen): {n} Mail-Notiz{'en' if n != 1 else ''} abgelegt"
        ergebnis = git("commit", "-q", "-m", kopf, "-m", "\n".join(f"- {p}" for p in pfade))
        if ergebnis.returncode != 0:
            print("Nichts zu committen.")
    voraus = git("rev-list", "--count", "origin/main..HEAD").stdout.strip()
    if voraus not in ("", "0"):
        if git("push", "-q", "origin", "main").returncode != 0:
            print("WARNUNG: Push fehlgeschlagen. Committet, aber nicht beim Mac.",
                  file=sys.stderr)
            return 1
        print(f"Veroeffentlicht: {git('rev-parse', '--short', 'HEAD').stdout.strip()} "
              f"({len(pfade)} neu, {voraus} Commit(s) geschoben)")
    return 0


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pruefe-zugang", action="store_true")
    ap.add_argument("--trockenlauf", action="store_true", help="nichts schreiben, nichts verschieben")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    pf = postfach()
    vault = vault_wurzel()
    if not os.path.isfile(os.path.join(vault, os.environ.get("VAULT_MARKER", "CLAUDE.md"))):
        print(f"ABBRUCH: '{vault}' ist keine Vault-Wurzel.", file=sys.stderr)
        return 2

    try:
        erlaubte = erlaubte_absender()
        mt = mail_token()
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2

    register, kollisionen = lade_register(vault)
    if kollisionen:
        print("WARNUNG: Kuerzel doppelt vergeben — betroffene bleiben unzugeordnet:",
              file=sys.stderr)
        for k, a1, a2 in kollisionen:
            print(f"  {k}: {a1}  UND  {a2}", file=sys.stderr)

    if a.pruefe_zugang:
        try:
            graph_mit_kopf(mt, "GET", f"/users/{pf}/mailFolders/inbox/messages?$select=id&$top=1")
        except Fehler as fehler:
            print(f"ZUGANG GESTOERT: {fehler}", file=sys.stderr)
            return 2
        print(f"Postfach {pf}: erreichbar. Allowlist: {len(erlaubte)} Adresse(n). "
              f"Register: {len(register)} Kuerzel.")
        return 0

    try:
        kennungen = ordner_kennungen(mt, pf, anlegen=not a.trockenlauf)
        arbeit = [(k, "inbox") for k in mail_koepfe(mt, pf, "inbox", a.limit)]
        if kennungen["ohne-zuordnung"]:
            arbeit += [(k, "ohne-zuordnung")
                       for k in mail_koepfe(mt, pf, kennungen["ohne-zuordnung"], a.limit)]
    except Fehler as fehler:
        print(f"ABBRUCH: {fehler}", file=sys.stderr)
        return 2
    print(f"{sum(1 for _, q in arbeit if q == 'inbox')} Mail(s) im Eingang, "
          f"{sum(1 for _, q in arbeit if q != 'inbox')} in ohne-zuordnung ({pf}).")
    if not arbeit:
        return 0

    zaehler = {"notiz": 0, "zeiger": 0, "schon_da": 0, "abgewiesen": 0, "ohne": 0,
               "liegt": 0, "fehler": 0}
    geschrieben, nachraeumen = [], []

    for kopf, quelle in arbeit:
        mid = kopf["id"]
        try:
            m = mail_lesen(mt, pf, mid)
        except Fehler as fehler:
            print(f"  [FEHLER ] Mail nicht lesbar: {fehler}", file=sys.stderr)
            zaehler["fehler"] += 1
            continue
        absender = ((m.get("from") or {}).get("emailAddress") or {}).get("address", "")
        betreff = m.get("subject") or ""
        empfangen = m.get("receivedDateTime") or ""
        wann = lokale_zeit(empfangen)
        kurz = f"{wann.strftime('%d.%m. %H:%M')} {betreff[:50]!r} von {absender}"

        ok, grund = gate_verdikt(m.get("internetMessageHeaders"), absender, erlaubte)
        if not ok:
            print(f"  [ABGEWIESEN] {kurz} — {grund}")
            if not a.trockenlauf:
                verschieben(mt, pf, mid, kennungen["abgewiesen"])
            zaehler["abgewiesen"] += 1
            continue

        ziel_rel, kuerzel, thema, grund = zuordnen(betreff, register)
        if not ziel_rel:
            if quelle == "inbox":
                print(f"  [OHNE   ] {kurz} — {grund}; nach ohne-zuordnung")
                if not a.trockenlauf:
                    verschieben(mt, pf, mid, kennungen["ohne-zuordnung"])
                zaehler["ohne"] += 1
            else:
                print(f"  [LIEGT  ] {kurz} — {grund}; bleibt in ohne-zuordnung")
                zaehler["liegt"] += 1
            continue

        text, gesamt = rumpf_kappen(((m.get("body") or {}).get("content")) or "")
        anhaenge = []
        if m.get("hasAttachments"):
            try:
                anhaenge = anhang_namen(mt, pf, mid)
            except Fehler as fehler:
                print(f"             WARNUNG: Anhaenge nicht lesbar ({fehler}).", file=sys.stderr)
        mail_id = m.get("internetMessageId") or ""

        # Marker `Ressource:`: Zeiger statt Notiz. Die URL kommt aus dem
        # Rumpf, der Marker aus dem Betreff — der Rumpf steuert nichts (F3).
        ist_ressource, titel = ressource_erkennen(thema)
        url, kontext = None, text
        if ist_ressource:
            url, kontext = url_herausloesen(text)
            if not url:
                befund = f"Marker '{MARKER_RESSOURCE}:' im Betreff, aber keine URL im Rumpf"
                if quelle == "inbox":
                    print(f"  [OHNE   ] {kurz} — {befund}; nach ohne-zuordnung")
                    if not a.trockenlauf:
                        verschieben(mt, pf, mid, kennungen["ohne-zuordnung"])
                    zaehler["ohne"] += 1
                else:
                    print(f"  [LIEGT  ] {kurz} — {befund}; bleibt in ohne-zuordnung")
                    zaehler["liegt"] += 1
                continue
        name = f"[{kuerzel}] {MARKER_RESSOURCE} {titel}" if ist_ressource else f"[{kuerzel}] {thema}"
        stamm = f"{wann.strftime('%Y-%m-%d')} {sichere_dateiname(name)}"
        ordner_rel = os.path.join(ziel_rel, "Notizen")
        try:
            pfad_rel, schon_da = freier_pfad(vault, ordner_rel, stamm, mail_id, wann)
        except Fehler as fehler:
            print(f"  [FEHLER ] {kurz}: {fehler}", file=sys.stderr)
            zaehler["fehler"] += 1
            continue
        art = "ZEIGER " if ist_ressource else "NOTIZ  "
        print(f"  [{art}] {kurz} -> {pfad_rel}  ({grund}; {len(kontext)} Zeichen"
              f"{'; artefakt: ' + url if url else ''}"
              f"{', ' + str(len(anhaenge)) + ' Anhang/Anhaenge nicht uebernommen' if anhaenge else ''})")

        if a.trockenlauf:
            m_meldung, _ = materialisiere_personen_ordner(vault, ziel_rel, True)
            if m_meldung:
                print(f"             {m_meldung}")
            continue

        m_meldung, m_pfade = materialisiere_personen_ordner(vault, ziel_rel, False)
        if m_meldung:
            print(f"             {m_meldung}")
        geschrieben.extend(m_pfade)

        if schon_da:
            print("             Notiz liegt schon (gleiche mail_id) — nur nachraeumen.")
            zaehler["schon_da"] += 1
        else:
            os.makedirs(os.path.join(vault, ordner_rel), exist_ok=True)
            if ist_ressource:
                # Hub erst JETZT aufloesen — nach der Materialisierung, sonst
                # fehlt bei einer Person die Hub-Datei noch.
                inhalt = baue_zeiger(titel, kuerzel, hub_link(vault, ziel_rel, kuerzel),
                                     betreff, absender, empfangen, url, kontext,
                                     gesamt > len(text), anhaenge, mail_id)
            else:
                inhalt = baue_notiz(thema, kuerzel, betreff, absender, empfangen,
                                    text, gesamt, anhaenge, mail_id)
            with open(os.path.join(vault, pfad_rel), "w", encoding="utf-8") as fh:
                fh.write(inhalt)
            geschrieben.append(pfad_rel)
            zaehler["zeiger" if ist_ressource else "notiz"] += 1
        nachraeumen.append(mid)

    print(f"\nNotizen: {zaehler['notiz']}, Zeiger: {zaehler['zeiger']}, "
          f"schon da: {zaehler['schon_da']}, "
          f"abgewiesen: {zaehler['abgewiesen']}, ohne Zuordnung: {zaehler['ohne']} "
          f"(liegen geblieben: {zaehler['liegt']}), Fehler: {zaehler['fehler']}.")
    if a.trockenlauf:
        print("Trockenlauf — nichts geschrieben, nichts verschoben.")
        return 0

    if nachraeumen and veroeffentliche(vault, geschrieben) != 0:
        print("Mails bleiben im Eingang, bis die Veroeffentlichung gelingt.", file=sys.stderr)
        return 1
    for mid in nachraeumen:
        verschieben(mt, pf, mid, kennungen["verarbeitet"])
    if nachraeumen:
        print(f"{len(nachraeumen)} Mail(s) nach verarbeitet.")
    return 1 if zaehler["fehler"] else 0


if __name__ == "__main__":
    sys.exit(main())
