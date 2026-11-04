export function getSubmissionTargets(project) {
  if (!project) return []
  if ((project.tasks || []).length > 0) {
    return project.tasks.map((task, idx) => ({
      ...task,
      indexLabel: `Aufgabe ${idx + 1}`
    }))
  }
  return [{ ...project, indexLabel: 'Projektabgabe' }]
}

export function getParticipation(project, targetId, studentId) {
  if (!project || !studentId) return null
  return (
    (project.participations || []).find(
      (participation) =>
        participation.project === targetId &&
        participation.student === Number(studentId)
    ) || null
  )
}

export function getStudentSubmissionStatus(project, studentId) {
  const targets = getSubmissionTargets(project)
  const total = targets.length
  let done = 0
  let hasParticipation = false

  for (const target of targets) {
    const participation = getParticipation(project, target.id, studentId)
    if (participation) hasParticipation = true
    if (participation?.is_done) done += 1
  }

  if (total > 0 && done === total) {
    return { label: 'Abgegeben', variant: 'badge-success' }
  }
  if (done > 0) {
    return { label: `${done}/${total} abgegeben`, variant: 'badge-warning' }
  }
  if (hasParticipation) {
    return { label: 'Entwurf', variant: 'badge-warning' }
  }
  return { label: 'Offen', variant: 'badge-neutral' }
}

export function getStudentEvaluationStatus(project, studentId) {
  const evaluations = (project?.evaluations || []).filter(
    (evaluation) => evaluation.student === Number(studentId)
  )
  if (
    evaluations.some(
      (evaluation) => evaluation.is_released || evaluation.eval_released
    )
  ) {
    return { label: 'bewertet', variant: 'badge-success' }
  }
  if (evaluations.length > 0) {
    return { label: 'Bewertung offen', variant: 'badge-warning' }
  }
  return { label: 'nicht bewertet', variant: 'badge-neutral' }
}

export function getStudentCombinedStatus(project, studentId) {
  const submission = getStudentSubmissionStatus(project, studentId)
  const evaluation = getStudentEvaluationStatus(project, studentId)
  let variant = 'badge-neutral'

  if (submission.label === 'Abgegeben' && evaluation.label === 'bewertet') {
    variant = 'badge-success'
  } else if (submission.label === 'Abgegeben') {
    variant = 'badge-info'
  } else if (submission.label !== 'Offen') {
    variant = 'badge-warning'
  }

  return {
    label: `${submission.label} · ${evaluation.label}`,
    variant
  }
}
