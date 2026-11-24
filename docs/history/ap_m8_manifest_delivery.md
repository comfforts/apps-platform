# AP-M8 manifest-driven delivery record

Status: historical; superseded by AP-M9

At source revision `7b6678a7f0b3036d427517dad6bc3bec876d1a44`:

- AP-M8-W1 had been owner-accepted and merged. It described protected environments, operation
  identities, state lineages, multi-stage deployment, DNS/TLS, and evidence checkpoints.
- AP-M8-W2 had implemented the closed operator-input-manifest schema, pure loader, canonical
  digest, append-only predecessor validation, a read-only command, and synthetic tests.
- no real operator manifest had been accepted;
- no AP-M8 repository setting, federation identity, backend, provider resource, image, DNS record,
  certificate, traffic change, deployment, or Live evidence had been created; and
- AP-M8-W3 through AP-M8-W12 had not started.

The hand-authored manifest required too many operator-supplied derived and provider-owned facts and
did not provide the intended human-operable product. ADR-010 retired that interface. AP-M9 replaces
it with small environment profiles and an interactive lifecycle that discovers read-only facts,
presents exact changes, obtains bounded approvals, performs ordered operations, and records
readbacks.

AP-M9-W2 removed the schema, example, command, validator, loader, exports, and dedicated tests from
the active tree. The source revision above remains the exact implementation record; removal does
not change the factual AP-M8 delivery evidence or create operational authority.

The old AP-EVAL-M8 and standalone AP-EVAL-M9 definitions have no result and provide no current
claim. The complete historical text and implementation are recoverable from Git at the revision
above; this record deliberately does not duplicate obsolete instructions.
