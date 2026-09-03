# Downstream publication gate

Every future catalog, webshop, marketplace or ERP publisher must call
`require_publishable()` from
`app.modules.suppliers.downstream_publication_policy` with the complete outgoing
batch before performing its first external write.

The policy is fail-closed. A Delta item is blocked when any of these conditions
is true:

- `downstream_blocked` is true;
- `requires_manual_approval` is true;
- `DOWNSTREAM_ITEM_BLOCKED` is present in its anomaly flags;
- there is no current Snapshot Item to publish;
- either required boolean is missing or is not a boolean.

The final rule deliberately blocks historical Delta rows created before this
contract and any future producer which forgets to make an explicit decision.
Publishers must not duplicate, weaken or locally reinterpret the policy.

`require_publishable()` evaluates the whole batch first and raises
`DownstreamPolicyViolation` containing the rejected Delta IDs. The publisher
must make no external call before that check. Partial approval, durable approval
history, operator identity and automatic release after a corrected supplier
feed belong to the review workflow; they must result in a new explicit decision
rather than bypassing this gate.

Snapshot archive export is not downstream product publication and remains a
separate integrity-preserving operation.
