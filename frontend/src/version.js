// App version from the repository VERSION file and the injected git sha
// (set as VITE_APP_VERSION / VITE_GIT_SHA at build time, see Dockerfile).
// Empty outside of stamped builds (npm run dev shows just "Alpha").
export const appVersion = import.meta.env.VITE_APP_VERSION || ''
export const gitSha = import.meta.env.VITE_GIT_SHA || ''

export const versionLabel = [
  appVersion ? `v${appVersion}` : '',
  gitSha,
]
  .filter(Boolean)
  .join(' · ')
