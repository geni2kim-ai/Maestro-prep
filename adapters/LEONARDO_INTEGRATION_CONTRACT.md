# Generic external route adapter

The coordinator consumes its documented normalized `LEONARDO_ROUTE_DECISION_V1` JSON and captured input/output/policy hashes. This is **not** an assertion that an external routing implementation emits this schema natively.

A separately owner-approved local adapter must authenticate installed router bytes and effective policy, preserve original output, and bind the normalized route to the current work unit and captured hash. Provider execution, routing semantics and policy enforcement require private local receipts and independent verification. No actual node name, path, private skill or historical export filename is embedded in this repository. Routing cannot disable the mandatory O-Prep gate or grant deploy authority.
