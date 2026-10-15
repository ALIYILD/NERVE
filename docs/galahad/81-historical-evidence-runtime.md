# Historical receipt replay and runtime portability

Some archived development receipts were produced on macOS x86_64 with CPython 3.10. Their validators deliberately require bit-exact schedule hashes and arithmetic, and their source manifests bind the original implementations. A seed alone does not pin platform math libraries. CPython 3.12 also changed floating-point summation. Replaying these receipts on Linux/Python 3.12 therefore does not establish receipt validity.

The `historical-evidence` workflow runs the archived evidence and tamper-rejection suites on `macos-15-intel` / Python 3.10. It asserts the environment before testing, so this job cannot pass by skipping archived evidence. It verifies existing receipts; it does not regenerate them, rerun consumed studies, or authorize promotion. This job must pass before merging research changes.

Those archived-receipt tests report explicit skips on other environments. Linux CI continues testing freshly generated synthetic evidence and the remaining functionality. A Linux test-suite pass alone does not establish historical receipt replay compatibility. Archived diagnostic APIs continue to fail closed on incompatible receipts; no comparison tolerances or source pins were relaxed.

The WorldCore diagnostic separately normalizes AST serialization to its registered Python 3.10 shape: optional None fields are omitted, empty lists retained, and the new empty `type_params` field ignored. Nonempty generic parameters and all other semantic changes still change the fingerprint. A Linux matrix exercises this contract and rejection tests on Python 3.10, 3.12 and 3.13.

A corrupt nested JSON list may be rejected during parsing or during exact object-schema validation, depending on interpreter recursion behavior. The test accepts either explicit rejection, and still checks degraded status, refused reads/writes and unchanged database bytes.

Future portable research protocols should register canonical exogenous inputs and explicit numerical reduction semantics before execution. This change does not redefine any historical scientific protocol.

The complete memory readiness workflow also runs in the archived-receipt environment: its existing rule rejects any skipped required test. This rule is unchanged. Linux research smoke, coverage and the diagnostic matrix remain separate checks. The Intel runner label follows [GitHub's supported runner catalog](https://docs.github.com/en/actions/reference/runners/github-hosted-runners).

The aggregate verification wrapper permits 1,800 seconds for the full multi-process test suite; its former 300-second limit was shorter than the observed CI CPU suite. Individual module limits remain unchanged. CI runs that CPU suite once and reuses its verification receipt for readiness, instead of executing the same suite twice. No test selection or acceptance rule changes.
