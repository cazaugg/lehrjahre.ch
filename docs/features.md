# Features

## Navigation

- Sidebar-Navigation
- Untermenü Lerndokumentation
- Rollen-Badge (Ausbildner/Lernende/r)
- Benutzerübersicht
- Abmelden

## Login

- Anmeldung mit E-Mail und Passwort
- Demo-Zugänge
- Fehlermeldungen

## Projekte, Themen & Praktika

Zugriff:

- Vorgesetzter: Eigene Projekte und Projekte seiner Lernenden
- Lernende: Nur Projekte bei denen Mitgearbeitet wird

| Feature             | Vorgesetzter                     | Lernende                               |
| ------------------- | -------------------------------- | -------------------------------------- |
| Projekt             | Bearbeiten + Erstellen + Löschen | Anzeigen wenn Planung freigegeben      |
| Projektplanung      | Bearbeiten                       | Anzeigen wenn Planung freigegeben      |
| Projektdurchführung | Anzeigen                         | Bearbeiten solange nicht abgeschlossen |
| Projekt abgeben     | Ändern                           | Kann Abgeben aber nicht wider öffnen   |
| Projektbewertung    | Bearbeiten                       | Anzeige wenn freigeben                 |

## Lerndokumentation

Zugriff:

- Vorgesetzter: Angaben/Dokumente seiner Lernenden
- Lernende: Nur eigene Angaben/Dokumente

| Feature                 | Vorgesetzter                  | Lernende                      |
| ----------------------- | ----------------------------- | ----------------------------- |
| Noten                   | Erfassen, Bearbeiten, Löschen | Erfassen, Bearbeiten, Löschen |
| Zeugnisse               | Erfassen, Bearbeiten, Löschen | Erfassen, Bearbeiten          |
| Ausbildungsgespräche    | Erfassen, Bearbeiten, Löschen | Anzeigen                      |
| Lernjournal Eintrag     | Anzeigen                      | Erfassen, Bearbeiten, Löschen |
| Lernjournal Rückmeldung | Erfassen, Bearbeiten, Löschen | Anzeigen                      |

## Wissen & Notizen

Zugriff:

- Vorgesetzter: Eigne Einträge und Einträge seiner Lernenden
- Lernende: Nur eigene Einträge

| Feature         | Vorgesetzter                  | Lernende                      |
| --------------- | ----------------------------- | ----------------------------- |
| Eigene Einträge | Erfassen, Bearbeiten, Löschen | Erfassen, Bearbeiten, Löschen |
| Fremde Einträge | Anzeigen                      | ---                           |

## Firmen

- Jede Person gehört zu genau einer Firma.
- Die Firmen-E-Mail muss zur E-Mail-Domain der Firma passen.
- Die Firma einer Person kann nicht geändert werden.
- Neue Personen übernehmen die Adresse der Firma als Standard für den Betriebsstandort.
- Firmen werden über den Seed oder die CLI (`python -m backend.companies`) verwaltet.

## Personen

Vorgesetzte:

- Eigene Kontaktdaten bearbeiten (Firma, Schule und Private)
- Kontaktdaten anderen Vorgesetzter für Schule und Firma anzeigen, nicht aber Privat
- Kontaktdaten Schule und Firma aller Lernenden anzeigen
- Alle Kontaktdaten von unterstellten Lernenden anzeigen und bearbeiten
- Dokumente untergebener Lernender anzeigen und bearbeiten (Lehrvertrag/Bewerbung)

Lernende:

- Eigene Kontaktdaten anzeigen (Firma, Schule und Private)
- Kontaktdaten von allen Vorgesetzten für Schule und Firma anzeigen, nicht aber Privat
- Kontaktdaten Schule und Firma aller Lernenden anzeigen, nicht aber Privat
- Eigene Dokumente anzeigen (Lehrvertrag/Bewerbung)

> Das Profilbild gehört zu den Kontaktdaten der Firma

## Account

- Alle: Eigenes Profilfoto hochladen
- Alle: Passwort ändern
- Alle: Eigene Kontaktangaben anzeigen
- Nur Vorgesetzte: Eigene Kontaktangaben bearbeiten
