#!/usr/bin/env node
// Local dev orchestrator for lehrjahre.ch — zero dependencies.
//
//   npm run dev
//   npm run dev -- --api-port 5001 --web-port 5174
//   npm run setup
//
// Options:
//   --force         (seed only) delete the demo company and its data folder,
//                   then reseed everything from scratch
//   --api-port N    prefer this Flask port (default 5000)
//   --web-port N    prefer this Vite port (default 5173)
//   --strict-port   fail instead of shifting when a port is taken
//   --no-install    skip uv sync / npm install
//   --help, -h      show this help

import { spawn, spawnSync, execFileSync } from 'node:child_process'
import { existsSync, mkdirSync, readFileSync } from 'node:fs'
import { get } from 'node:http'
import { createServer } from 'node:net'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const IS_WIN = process.platform === 'win32'
const NPM = IS_WIN ? 'npm.cmd' : 'npm'
const FRONTEND = path.join(ROOT, 'frontend')
const VENV_PY = path.join(
  ROOT,
  '.venv',
  IS_WIN ? 'Scripts' : 'bin',
  IS_WIN ? 'python.exe' : 'python',
)
const DEFAULT_API_PORT = 5000
const DEFAULT_WEB_PORT = 5173

const rawArgs = process.argv.slice(2)
const command = ['setup', 'seed', 'help'].includes(rawArgs[0])
  ? rawArgs.shift()
  : 'dev'
const flags = new Set()
let apiPortFlag = null
let webPortFlag = null

for (let i = 0; i < rawArgs.length; i++) {
  const arg = rawArgs[i]
  if (arg === '--api-port') apiPortFlag = Number(rawArgs[++i])
  else if (arg === '--web-port') webPortFlag = Number(rawArgs[++i])
  else if (arg === '-h') flags.add('--help')
  else if (arg.startsWith('-')) flags.add(arg)
}
const has = (flag) => flags.has(flag)

function validPort(value, flag) {
  if (!Number.isInteger(value) || value < 1 || value > 65535) {
    fail(`${flag} must be a port between 1 and 65535`)
  }
  return value
}
if (apiPortFlag !== null) apiPortFlag = validPort(apiPortFlag, '--api-port')
if (webPortFlag !== null) webPortFlag = validPort(webPortFlag, '--web-port')

if (command === 'help' || has('--help')) {
  const lines = readFileSync(fileURLToPath(import.meta.url), 'utf8').split('\n')
  const end = lines.findIndex((line) => line.startsWith('import '))
  process.stdout.write(lines.slice(0, end > 0 ? end : lines.length).join('\n') + '\n')
  process.exit(0)
}

function fail(message) {
  process.stderr.write(`error ${message}\n`)
  process.exit(1)
}

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function checkNode() {
  const [major, minor] = process.versions.node.split('.').map(Number)
  if (major < 26) {
    fail(`Node >= 26.0.0 required (found ${process.versions.node})`)
  }
}

function commandExists(cmd) {
  return spawnSync(IS_WIN ? 'where' : 'which', [cmd], { stdio: 'ignore' }).status === 0
}

function runSync(cmd, args, options = {}) {
  return spawnSync(cmd, args, { stdio: 'inherit', ...options })
}

// ---------------------------------------------------------------------------
// ports
// ---------------------------------------------------------------------------

function probeHost(port, host) {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.once('listening', () => {
      const actual = server.address().port
      server.close(() => resolve(actual))
    })
    server.listen(port, host)
  })
}

// Check IPv4 and IPv6 loopback: a server bound to either one must be detected.
async function portFree(port) {
  for (const host of ['127.0.0.1', '::1']) {
    try {
      await probeHost(port, host)
    } catch (err) {
      if (['EAFNOSUPPORT', 'EADDRNOTAVAIL', 'ENOTFOUND'].includes(err.code)) continue
      if (err.code === 'EADDRINUSE' || err.code === 'EACCES') return false
      throw err
    }
  }
  return true
}

async function findFreePort(preferred, label) {
  for (let port = preferred; port <= preferred + 100; port++) {
    if (await portFree(port)) return port
    if (has('--strict-port')) {
      fail(`${label} port ${port} is in use (--strict-port). Free it and retry.`)
    }
  }
  fail(`no free ${label} port near ${preferred}`)
}

function httpOk(url, timeout = 500) {
  return new Promise((resolve) => {
    const req = get(url, (res) => {
      res.resume()
      resolve(res.statusCode === 200)
    })
    req.setTimeout(timeout, () => {
      req.destroy()
      resolve(false)
    })
    req.on('error', () => resolve(false))
  })
}

async function waitForApi(port, timeoutMs = 30000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await httpOk(`http://127.0.0.1:${port}/api/health`)) return true
    await sleep(250)
  }
  return false
}

// ---------------------------------------------------------------------------
// dependency bootstrap
// ---------------------------------------------------------------------------

function ensureBackend() {
  if (!commandExists('uv')) {
    fail('uv not found. Install it: https://docs.astral.sh/uv')
  }
  if (existsSync(VENV_PY)) return
  if (has('--no-install')) {
    fail('.venv is missing and --no-install is set. Run `uv sync` first.')
  }
  process.stdout.write('[setup] .venv missing -> uv sync\n')
  if (runSync('uv', ['sync'], { cwd: ROOT }).status !== 0) fail('uv sync failed')
}

function ensureFrontend() {
  if (!commandExists('npm')) fail('npm not found (Node >= 26.0.0 required)')
  if (existsSync(path.join(FRONTEND, 'node_modules'))) return
  if (has('--no-install')) {
    fail('frontend/node_modules is missing and --no-install is set. Run `npm ci` in frontend/.')
  }
  const useCi = existsSync(path.join(FRONTEND, 'package-lock.json'))
  process.stdout.write(`[setup] installing frontend deps (npm ${useCi ? 'ci' : 'install'})\n`)
  const result = runSync(NPM, [useCi ? 'ci' : 'install'], {
    cwd: FRONTEND,
    shell: IS_WIN,
  })
  if (result.status !== 0) fail('frontend dependency install failed')
}

// ---------------------------------------------------------------------------
// process plumbing
// ---------------------------------------------------------------------------

let backend = null
let frontend = null
let shuttingDown = false

function stream(child, tag) {
  const pipe = (source, sink) => {
    if (!source) return
    let buffer = ''
    source.setEncoding('utf8')
    source.on('data', (chunk) => {
      buffer += chunk
      const lines = buffer.split(/\r?\n/)
      buffer = lines.pop() ?? ''
      for (const line of lines) sink.write(`${tag} ${line}\n`)
    })
    source.on('end', () => {
      if (buffer) sink.write(`${tag} ${buffer}\n`)
    })
  }
  pipe(child.stdout, process.stdout)
  pipe(child.stderr, process.stderr)
}

function killTree(pid) {
  if (!pid) return
  if (IS_WIN) {
    spawnSync('taskkill', ['/pid', String(pid), '/T', '/F'], { stdio: 'ignore' })
    return
  }
  try {
    process.kill(-pid, 'SIGTERM')
  } catch {
    try {
      process.kill(pid, 'SIGTERM')
    } catch {
      /* already gone */
    }
  }
}

function shutdown(code = 0) {
  if (shuttingDown) return
  shuttingDown = true
  killTree(backend?.pid)
  killTree(frontend?.pid)
  setTimeout(() => process.exit(code), 300)
}

function supervise(child, tag) {
  child.on('error', (err) => {
    process.stderr.write(`[${tag}] ${err.message}\n`)
    shutdown(1)
  })
  child.on('exit', (code, signal) => {
    if (shuttingDown) return
    process.stdout.write(`[${tag}] stopped (${code ?? signal})\n`)
    shutdown(code ?? 1)
  })
}

process.on('SIGINT', () => {
  process.stdout.write('\n')
  shutdown(0)
})
process.on('SIGTERM', () => shutdown(0))
process.on('uncaughtException', (err) => {
  process.stderr.write(`${err?.stack ?? err}\n`)
  shutdown(1)
})

// ---------------------------------------------------------------------------
// commands
// ---------------------------------------------------------------------------

function cmdSetup() {
  checkNode()
  mkdirSync(path.join(ROOT, 'data'), { recursive: true })
  ensureBackend()
  ensureFrontend()
  process.stdout.write('setup complete\n')
}

function cmdSeed() {
  checkNode()
  mkdirSync(path.join(ROOT, 'data'), { recursive: true })
  ensureBackend()
  // `npm run seed --force` is also accepted: npm doesn't forward flags after
  // a script name without `--`, but exposes them as npm_config_* env vars.
  const force = has('--force') || process.env.npm_config_force != null
  const args = ['run', 'python', '-m', 'backend.seed']
  if (force) args.push('--force')
  const result = spawnSync('uv', args, {
    cwd: ROOT,
    env: {
      ...process.env,
      LEHRJAHRE_ENV: 'development',
      LEHRJAHRE_DEBUG: '1',
      COOKIE_SECURE: 'false',
      SECRET_KEY: process.env.SECRET_KEY || 'dev-only-seed-key',
    },
    stdio: 'inherit',
  })
  process.exit(result.status ?? 1)
}

async function cmdDev() {
  checkNode()
  mkdirSync(path.join(ROOT, 'data'), { recursive: true })

  ensureBackend()
  ensureFrontend()

  const wantedApi = apiPortFlag ?? DEFAULT_API_PORT
  const wantedWeb = webPortFlag ?? DEFAULT_WEB_PORT
  const apiPort = await findFreePort(wantedApi, 'API')
  let webPort = await findFreePort(wantedWeb, 'Web')
  if (webPort === apiPort) webPort = await findFreePort(webPort + 1, 'Web')

  const apiNote = apiPort !== wantedApi ? ` (${wantedApi} busy)` : ''
  const webNote = webPort !== wantedWeb ? ` (${wantedWeb} busy)` : ''

  process.stdout.write(
    [
      '',
      'lehrjahre dev',
      `  API  http://127.0.0.1:${apiPort}${apiNote}`,
      `  Web  http://127.0.0.1:${webPort}${webNote}   <- open this`,
      '  Ctrl+C stops both.',
      '',
    ].join('\n') + '\n',
  )

  // Stamp the dev build like production does (Docker sets these in the
  // frontend-build stage): semver from VERSION + current git commit.
  const appVersion = readFileSync(path.join(ROOT, 'VERSION'), 'utf8').trim()
  let gitSha = ''
  try {
    gitSha = execFileSync('git', ['rev-parse', '--short', 'HEAD'], {
      cwd: ROOT,
      encoding: 'utf8',
    }).trim()
  } catch {
    // No git available / not a repository: the version label stays reduced.
  }

  backend = spawn(VENV_PY, ['-m', 'backend.app'], {
    cwd: ROOT,
    env: {
      ...process.env,
      LEHRJAHRE_PORT: String(apiPort),
      LEHRJAHRE_ENV: 'development',
      LEHRJAHRE_DEBUG: '1',
      COOKIE_SECURE: 'false',
      SECRET_KEY: process.env.SECRET_KEY || 'dev-only-local-key',
      PYTHONUNBUFFERED: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: !IS_WIN,
  })
  stream(backend, '[api] ')
  supervise(backend, 'api')

  frontend = spawn(NPM, ['run', 'dev', '--', '--port', String(webPort)], {
    cwd: FRONTEND,
    env: {
      ...process.env,
      LEHRJAHRE_API_PORT: String(apiPort),
      VITE_APP_VERSION: appVersion,
      VITE_GIT_SHA: gitSha,
    },
    stdio: ['ignore', 'pipe', 'pipe'],
    shell: IS_WIN,
    detached: !IS_WIN,
  })
  stream(frontend, '[web] ')
  supervise(frontend, 'web')

  if (await waitForApi(apiPort)) {
    process.stdout.write(`[api] ready on http://127.0.0.1:${apiPort}\n`)
  } else if (!shuttingDown) {
    process.stdout.write('[api] not responding yet — check the log above\n')
  }
}

const COMMANDS = { dev: cmdDev, setup: cmdSetup, seed: cmdSeed }
const run = COMMANDS[command]
if (!run) fail(`unknown command "${command}"`)

try {
  await run()
} catch (err) {
  fail(err?.message ?? String(err))
}
