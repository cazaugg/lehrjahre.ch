import MarkdownIt from 'markdown-it'
import texmath from 'markdown-it-texmath'
import katex from 'katex'

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
})

md.use(texmath, {
  engine: katex,
  delimiters: ['dollars', 'brackets'],
  katexOptions: {
    throwOnError: false,
    strict: 'ignore',
    trust: false
  }
})

// Shift headings down one level so the preview keeps the previous visual scale
// (# -> h2, ## -> h3, ### -> h4) instead of competing with the page title.
const defaultHeadingOpen =
  md.renderer.rules.heading_open ||
  ((tokens, idx, options, env, self) =>
    self.renderToken(tokens, idx, options))
const defaultHeadingClose =
  md.renderer.rules.heading_close ||
  ((tokens, idx, options, env, self) =>
    self.renderToken(tokens, idx, options))

function shiftHeadingTag(token) {
  const level = Number(token.tag.slice(1))
  token.tag = `h${Math.min(level + 1, 6)}`
}

md.renderer.rules.heading_open = (tokens, idx, options, env, self) => {
  shiftHeadingTag(tokens[idx])
  return defaultHeadingOpen(tokens, idx, options, env, self)
}

md.renderer.rules.heading_close = (tokens, idx, options, env, self) => {
  shiftHeadingTag(tokens[idx])
  return defaultHeadingClose(tokens, idx, options, env, self)
}

// Open links in a new tab so clicking linked documents/URLs never loses editor state.
const defaultLinkOpen =
  md.renderer.rules.link_open ||
  ((tokens, idx, options, env, self) =>
    self.renderToken(tokens, idx, options))

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  const token = tokens[idx]
  const href = token.attrGet('href') || ''
  if (href && !href.startsWith('#')) {
    token.attrSet('target', '_blank')
    token.attrSet('rel', 'noopener noreferrer')
  }
  return defaultLinkOpen(tokens, idx, options, env, self)
}

export function renderMarkdown(raw) {
  return md.render(String(raw || ''))
}
