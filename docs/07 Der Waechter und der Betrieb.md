# 07 — Der Wächter und der Betrieb

## Zwei Ebenen der Aufsicht, bewusst getrennt

| Frage | wer beantwortet sie |
|---|---|
| **Läuft der Job überhaupt?** | Lebenszeichen (`heartbeat.sh`) |
| **Stimmt der Inhalt?** | Wächter (`remarkable_wachhund.py`) |

Ein Lebenszeichen sieht, dass ein Job gelaufen ist. Es sieht nicht, dass eine Datei in
SharePoint verschoben wurde und zwanzig Notizen jetzt ins Leere zeigen.

## Das Lebenszeichen

Jeder Lauf hinterlässt einen Zeitstempel. Bleibt er aus, meldet der Nachtbericht.

**Ein Job ohne Lebenszeichen ist ein Job, den man nicht hat.** Der Satz ist nicht
rhetorisch: In einem Fall waren vier Routinen **sechs Wochen lang tot**, weil ihr
Statusbericht in einer Datei stand, die niemand öffnete.

Der Wrapper übernimmt auch die Fehlerklasse: `rc 69` heisst «wiederholbar, nicht
melden», `rc 77` heisst «sofort melden».

## Der Wächter: drei Signale

| Signal | Schwelle | warum diese Schwelle |
|---|---|---|
| **Tote `artefakt:`-Links** | sofort | Ein toter Link ist immer ein Fehler. Es gibt keinen Grund zu warten |
| **«Ohne Zuordnung», veraltet** | ab 3 Tagen | **Frisch ist normal** — der Zuordner löst binnen Minuten. Ein Stapel, der Tage alt wird, wächst sonst unbemerkt |
| **Stiller Eingang** | ab 14 Tagen | Absicht oder Defekt. Der Wächter **fragt**, statt Stille als Normalzustand zu behandeln |

Er liest Vault und Bibliothek und **schreibt nichts** — läuft deshalb ohne Sperre.

### Höchstens eine Meldung je Befund

Ein Merker verhindert, dass derselbe tote Link jede Nacht erneut klingelt. Ohne ihn
wäre der Kanal nach einer Woche Rauschen.

## Stille bedeutet gesund

Der Melder wird **nicht** bei Erfolg aufgerufen. Zehn Jobs mal täglich wären über 300
Nachrichten im Monat, die alle dasselbe sagen. Nach zwei Wochen schaut niemand mehr hin
— und der Kanal ist so tot wie der Statusbericht, den er ersetzen sollte.

Gesendet wird bei Fehlschlag, bei Überfälligkeit, und **einmal täglich die Zeile, die
beweist, dass der Melder selbst noch lebt.**

Zwei Auflagen an den Kanal:

1. **Er hängt nicht an dem, was er überwacht.** Kein Vault-Zugriff, kein Git, nur
   ausgehendes HTTPS. Ein Bericht über einen kaputten Kanal, der über denselben Kanal
   läuft, ist keine Überwachung.
2. **Inhalte gehen nicht hinaus.** Kennungen und Fehlerlagen, keine Notiztitel.

> **Detail aus dem Melder, das teuer war:** Der Rückgabewert von `curl` beweist nichts —
> er ist 0, sobald *irgendeine* HTTP-Antwort kam, auch bei 401. Geprüft wird deshalb die
> Antwort selbst. Beim ersten Test meldete der Selbsttest Erfolg auf ein HTTP 401,
> weil hinter einer Negation `$?` den negierten Wert trägt. Genau die Klasse Fehler,
> gegen die dieser Kanal gebaut wurde.

## Der Zeitplan

| Job | Takt | Konto | Sperre |
|---|---|---|---|
| Abholer | alle 15 Min | Dienstkonto | nein — schreibt nicht ins Vault |
| Zuordner | alle 15 Min, verkettet | Dienstkonto | **ja** |
| Sprachnotiz | alle 4 h | Konto mit CLI-Anmeldung | **ja** |
| Wächter | nächtlich | Dienstkonto | nein — liest nur |
| Index | nächtlich | Dienstkonto | nein — liest Vault, schreibt SharePoint |

Vorlage: [`einrichtung/cron.beispiel`](../einrichtung/cron.beispiel)

## Die Sperre

Zwei Prozesse, die gleichzeitig ins Vault schreiben, erzeugen einen Zwischenstand, den
der eine als den eigenen einliest.

**Die Grenze:** *Startest du ein Programm, das viele Dateien anfasst?* Ja heisst Sperre.
Eine einzelne Dateibearbeitung braucht keine — die Sperre minutenlang zu halten,
während jemand eine Notiz schreibt, legt alle Jobs still.

## Symptom → Ursache → erster Handgriff

| Symptom | wahrscheinliche Ursache | erster Handgriff |
|---|---|---|
| 403 auf das **eigene** Postfach | Policy-Durchsetzung kennt die Gruppenmitgliedschaft noch nicht | **warten und erneut messen**, Stunden. Nicht schrauben |
| Mail bleibt im Eingang liegen | Anhang > 25 MB oder Upload-Fehler | Log lesen, der Grund steht als `[FEHLER]`-Zeile drin |
| alles landet in `abgewiesen` | DMARC-Problem beim Absender — **oder ein Angriffsversuch** | `Authentication-Results` einer betroffenen Mail ansehen |
| «Bibliothek nicht gefunden» | umbenannt, oder der Site-Grant fehlt | Grant prüfen: `Sites.Selected` allein gewährt nichts |
| Meldung «TOTE LINKS» | Dokument verschoben oder gelöscht | Datei zurücklegen oder Notiz korrigieren |
| Meldung «OHNE ZUORDNUNG» | Dokument ohne gültiges Kürzel | **umbenennen** — der nächste Lauf holt die Notiz nach |
| Meldung «STILLER EINGANG» | seit 14 Tagen kam nichts | War das Absicht? Sonst Lebenszeichen des Abholers prüfen |
| Notizen erscheinen nicht im Hub | Abfrage-Block fehlt im Hub | Block ergänzen — die Notiz liegt richtig, sie wird nur nicht gezeigt |
