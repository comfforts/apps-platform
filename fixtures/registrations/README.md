# Reviewed fixture registrations

These complete Version 1 Registration Sets configure only the deterministic Fixture Applications.
They are independent from `contracts/test-vectors/` and provide no provider, Live, Adoption, or
Finance Assistant evidence.

Each `proposal.source_revision` is the lowercase SHA-256 digest of
`fixtures/applications.py` at the reviewed fixture release. `manifest.v1.json` records the ordered
generation paths and their expected canonical Registration Generation digests. The first
generation registers all three applications as active in one immutable candidate. Later
generations exercise the reviewed update, suspension, reactivation, attachment-replacement, and
retirement transitions authorized by the implementation plan. A candidate is not externally
visible until the active-generation pointer is atomically changed.
