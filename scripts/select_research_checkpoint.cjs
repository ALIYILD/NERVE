// Read-only checkpoint discovery, used by actions/github-script and unit tests.
const ARTIFACT = 'nerve-retrieval-checkpoint-v1';
const WORKFLOW = '.github/workflows/recursive-research.yml';

async function selectCheckpoint({ github, context }) {
  const repository = `${context.repo.owner}/${context.repo.repo}`;
  // Bound API work. Normally the latest successful run contains the artifact.
  for (let page = 1; page <= 2; page++) {
    const { data } = await github.rest.actions.listWorkflowRuns({
      ...context.repo, workflow_id: 'recursive-research.yml',
      branch: 'main', status: 'success', per_page: 50, page,
    });
    for (const run of data.workflow_runs) {
      if (run.id === context.runId || run.status !== 'completed' ||
          run.conclusion !== 'success' || run.head_branch !== 'main' ||
          run.path !== WORKFLOW || run.head_repository?.full_name !== repository ||
          !['schedule', 'workflow_dispatch'].includes(run.event)) continue;
      const response = await github.rest.actions.listWorkflowRunArtifacts({
        ...context.repo, run_id: run.id, per_page: 100,
      });
      const matches = response.data.artifacts.filter(a =>
        a.name === ARTIFACT && !a.expired &&
        Number.isSafeInteger(a.id) && a.id > 0 &&
        a.size_in_bytes > 0 && a.size_in_bytes <= 250000);
      if (matches.length > 1) throw new Error('Ambiguous research checkpoint artifacts');
      if (matches.length === 1) return { runId: run.id, artifactId: matches[0].id };
    }
    if (data.workflow_runs.length < 50) break;
  }
  return null;
}

module.exports = { selectCheckpoint };
