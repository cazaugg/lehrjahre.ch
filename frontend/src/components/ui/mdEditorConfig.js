import { config } from 'md-editor-v3'

// Custom German labels; missing keys fall back to the built-in English defaults.
config({
  editorConfig: {
    languageUserDefined: {
      'de-DE': {
        toolbarTips: {
          bold: 'Fett',
          underline: 'Unterstrichen',
          italic: 'Kursiv',
          strikeThrough: 'Durchgestrichen',
          title: 'Überschrift',
          sub: 'Tiefgestellt',
          sup: 'Hochgestellt',
          quote: 'Zitat / Hinweis',
          unorderedList: 'Aufzählung',
          orderedList: 'Nummerierte Liste',
          task: 'Aufgabenliste / Checkliste',
          codeRow: 'Inline-Code',
          code: 'Codeblock',
          link: 'Web-Link einfügen',
          image: 'Bild-URL einfügen',
          table: 'Tabelle einfügen',
          katex: 'Mathematische Formel ($…$)',
          revoke: 'Rückgängig',
          next: 'Wiederholen'
        },
        titleItem: {
          h1: 'Überschrift 1',
          h2: 'Überschrift 2',
          h3: 'Überschrift 3',
          h4: 'Überschrift 4',
          h5: 'Überschrift 5',
          h6: 'Überschrift 6'
        },
        katex: {
          inline: 'Inline-Formel ($…$)',
          block: 'Block-Formel ($$…$$)'
        },
        linkModalTips: {
          linkTitle: 'Link einfügen',
          imageTitle: 'Bild einfügen',
          descLabel: 'Beschreibung:',
          descLabelPlaceHolder: 'Beschreibung eingeben...',
          urlLabel: 'Adresse:',
          urlLabelPlaceHolder: 'https://...',
          buttonOK: 'Einfügen'
        },
        copyCode: {
          text: 'Code kopieren',
          successTips: 'Kopiert',
          failTips: 'Kopieren fehlgeschlagen'
        },
        footer: {
          markdownTotal: 'Zeichen',
          scrollAuto: 'Synchron scrollen'
        }
      }
    }
  }
})
