# Generic external route adapter

The coordinator consumes its documented normalized `LEONARDO_ROUTE_DECISION_V1` JSON and captured input/output/policy hashes. This is **not** an assertion that an external routing implementation emits this schema natively.

A separately owner-approved local adapter must authenticate installed router bytes and effective policy, preserve original output, and bind the normalized route to the current work unit and captured hash. Provider execution, routing semantics and policy enforcement require private local receipts and independent verification. No actual node name, path, private skill or historical export filename is embedded in this repository. Routing cannot disable the mandatory O-Prep gate or grant deploy authority.

## R1.4 raw output/capture consistency gate

A `LEONARDO_ROUTE_CAPTURE_V1` wrapper describing `READY` is not a substitute for the underlying local Leonardo route bytes. In addition to O-Prep's indexed byte checks, Maestro checks the recorded `router_output` artifact a second time immediately before candidate evaluation:

- The raw JSON must be an object with `execution_state=READY_FOR_LOCAL_CANDIDATE_WORK` and the JSON boolean `candidate_work_allowed=true`.
- `request.request_sha256` and `input_bindings.policy_sha256` must equal the captured task/policy digests.
- `guard.blocks` must be a list and must be empty. Missing, malformed, nonempty or blocked guard data means HOLD.
- The *same* output bytes must hash to `routing_output_sha256`. Any change since the preceding O-Prep check is HOLD.

These are minimal normalized evidence fields, not a claim that the privately installed Leonardo emits this public adapter schema. A separately approved adapter must preserve the original output bytes, map state without widening readiness and bind the exact input/policy hashes. Current synthetic tests emulate this shape; genuine Leonardo node execution is NOT_RUN. SHA agreement remains evidence consistency, not independent provenance.
