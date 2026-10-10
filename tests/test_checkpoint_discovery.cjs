const { test } = require('node:test');
const assert = require('node:assert/strict');
const { selectCheckpoint } = require('../scripts/select_research_checkpoint.cjs');
const context = { repo: { owner: 'ALIYILD', repo: 'NERVE' }, runId: 99 };
const good = { id: 10, status: 'completed', conclusion: 'success', head_branch: 'main',
  path: '.github/workflows/recursive-research.yml',
  head_repository: { full_name: 'ALIYILD/NERVE' }, event: 'schedule' };
const artifact = { id: 101, name: 'nerve-retrieval-checkpoint-v1', expired: false, size_in_bytes: 2000 };
function fixture(pages, artifacts = { 10: [artifact] }) {
  const queries = [], inspected = [];
  const github = { rest: { actions: {
    async listWorkflowRuns(query) {
      queries.push(query);
      return { data: { workflow_runs: pages[query.page - 1] || [] } };
    },
    async listWorkflowRunArtifacts(query) {
      inspected.push(query.run_id);
      return { data: { artifacts: artifacts[query.run_id] || [] } };
    },
  } } };
  return { github, context, queries, inspected };
}

test('restores only same-repository successful main scheduled/manual research', async () => {
  const f = fixture([[good]]);
  assert.deepEqual(await selectCheckpoint(f), { runId: 10, artifactId: 101 });
  assert.equal(f.queries[0].workflow_id, 'recursive-research.yml');
  assert.equal(f.queries[0].branch, 'main');
  assert.equal(f.queries[0].status, 'success');
});

test('rejects failed, foreign, other-workflow, PR and current runs before reading artifacts', async () => {
  const invalid = [ { id: 99 }, { conclusion: 'failure' }, { status: 'in_progress' },
    { head_branch: 'feature' }, { path: '.github/workflows/tests.yml' },
    { head_repository: { full_name: 'fork/NERVE' } }, { event: 'pull_request' } ];
  const f = fixture([[...invalid.map(change => ({ ...good, ...change })), good]]);
  assert.deepEqual(await selectCheckpoint(f), { runId: 10, artifactId: 101 });
  assert.deepEqual(f.inspected, [10]);
});

test('skips expired, oversized and wrongly named artifacts', async () => {
  const f = fixture([[{ ...good, id: 11 }, good]], {
    11: [{ ...artifact, expired: true }, { ...artifact, size_in_bytes: 250001 },
         { ...artifact, name: 'other' }], 10: [artifact],
  });
  assert.deepEqual(await selectCheckpoint(f), { runId: 10, artifactId: 101 });
});

test('paginates beyond the first 50 successful runs', async () => {
  const f = fixture([Array.from({ length: 50 }, (_, i) => ({ ...good, id: 1000 + i })), [good]]);
  assert.deepEqual(await selectCheckpoint(f), { runId: 10, artifactId: 101 });
  assert.equal(f.queries.length, 2);
});

test('missing history returns explicit cold-start/cache fallback', async () => {
  assert.equal(await selectCheckpoint(fixture([[]])), null);
});

test('API failures are not hidden as cold starts', async () => {
  const f = fixture([[]]);
  f.github.rest.actions.listWorkflowRuns = async () => { throw Error('unauthorized'); };
  await assert.rejects(() => selectCheckpoint(f), /unauthorized/);
});

test('duplicate eligible checkpoints fail closed', async () => {
  const f = fixture([[good]], { 10: [artifact, { ...artifact, id: 102 }] });
  await assert.rejects(() => selectCheckpoint(f), /Ambiguous/);
});
