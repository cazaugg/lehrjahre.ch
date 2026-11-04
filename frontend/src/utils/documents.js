const MARKDOWN_EXTENSIONS = ['md', 'txt', 'csv']
const EDITABLE_TEXT_EXTENSIONS = ['md', 'txt']
const IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg']

export function getDocumentExtension(filename = '') {
  const clean = String(filename).toLowerCase().split('?')[0]
  const dot = clean.lastIndexOf('.')
  return dot >= 0 ? clean.slice(dot + 1) : ''
}

/**
 * Returns how a document can be previewed.
 * 'markdown' | 'pdf' | 'docx' | 'image' | 'other'
 */
export function getDocumentKind(doc) {
  if (!doc) return 'other'
  if (doc.content) return 'markdown'

  const ext = getDocumentExtension(doc.filename || '')
  if (MARKDOWN_EXTENSIONS.includes(ext)) return 'markdown'
  if (ext === 'pdf') return 'pdf'
  if (ext === 'docx') return 'docx'
  if (IMAGE_EXTENSIONS.includes(ext)) return 'image'
  return 'other'
}

/** Markdown/text documents can be opened in the Markdown editor. */
export function isMarkdownEditable(doc) {
  if (!doc) return false
  return EDITABLE_TEXT_EXTENSIONS.includes(
    getDocumentExtension(doc.filename || '')
  )
}

export function getDocumentFileUrl(id) {
  return `/api/documents/${id}/file`
}

export function getDocumentDownloadUrl(id) {
  return `${getDocumentFileUrl(id)}?download=1`
}
