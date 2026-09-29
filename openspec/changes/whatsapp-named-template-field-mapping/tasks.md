# Tasks: Explicit WhatsApp Template Parameter Formats

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 550–800 authored additions + deletions |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: persisted format and local create/update validation; PR 2: fetch/sync preservation and diagnostics; PR 3: message serialization and notification guard |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

The estimate reflects changes across the DocType schema, shared parsing/validation and two distinct send paths, Meta import behavior, and focused regression tests. The exact diff may differ. Because the estimate is above the 400-line review budget and the delivery strategy is `ask-on-risk`, the orchestrator must obtain the user's chain-strategy decision before apply; this task plan does not choose it.

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Add persisted format/mapping/example fields, shared placeholder and JSON validation, and format-correct local create/update BODY examples while retaining positional compatibility. | PR 1 | `bench --site test_site run-tests --doctype "WhatsApp Templates"` | N/A for local validation; mocked Meta request assertions cover request construction. Live named create/update acceptance remains a pre-rollout prerequisite, not a substitute for these tests. | Revert the DocType and template-controller changes together; leave additive stored values intact and keep named-template use disabled until compatible code is restored. |
| 2 | Validate remote format/examples before hook-free upsert, preserve local mappings by variable name, and return per-template actionable invalid-import diagnostics without replacing a prior valid record with unusable data. | PR 2 | `bench --site test_site run-tests --doctype "WhatsApp Templates"` | Manual controlled non-production Meta fetch/sync round-trip to confirm actual format/example response shape; do not claim live acceptance from mocks. No remote call is authorized by this task plan. | Revert fetch/import changes; retain stored mapping/example metadata and restore the previous sync behavior without deleting additive fields. |
| 3 | Serialize message body values by explicit format and placeholder order; reject incomplete named values before dispatch; guard both notification entry points against `NAMED` while preserving positional/header/button behavior. | PR 3 | `bench --site test_site run-tests --doctype "WhatsApp Message"` and `bench --site test_site run-tests --doctype "WhatsApp Notification"` | N/A for deterministic local dispatch boundaries; mocked `notify()`/HTTP tests prove zero dispatch on rejection. Perform a controlled non-production send round-trip only after the Meta payload prerequisite is verified and explicit remote authorization is granted. | Revert sender and notification changes together; suspend named sends on the prior code while retaining additive template data. |

All focused commands require an initialized Frappe bench, `test_site`, MariaDB, and Redis. The configured full-suite command is `bench --site test_site run-tests --app frappe_whatsapp`; it has the same service prerequisites and is not available from a bare checkout. No independent Python test runner is configured.

## Phase 1: Template Fields and Local Contracts

- [ ] 1.1 Add `parameter_format`, `named_field_mapping`, and `named_example_values` to `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.json`, preserving the existing `for_doctype`, `field_names`, and `sample_values` fields and treating an empty legacy format as `POSITIONAL` without writeback.
- [ ] 1.2 Add shared format, placeholder, JSON-object, duplicate-key, and template validation helpers in `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py`; validate first-occurrence unique named identities, numeric positional indexes, stale/duplicate/missing values, malformed placeholders, and unsupported formats without relying on JSON object order.
- [ ] 1.3 Add format-specific BODY example construction to local create/update paths in `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py`; named examples use one `body_text_named_params` entry per unique variable, while positional examples keep the existing `body_text` shape. Preserve the current header/footer/button construction and validate before Meta I/O.
- [ ] 1.4 Extend `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/test_whatsapp_templates.py` to assert default/explicit format behavior, repeated-variable collapse, malformed and duplicate JSON rejection, named example persistence and payload shape, positional compatibility, and unchanged header/button payloads using mocked Meta requests.

## Phase 2: Fetch and Synchronization Safety

- [ ] 2.1 In `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py`, parse and validate remote format and BODY example data before `upsert_doc_without_hooks()`; treat an absent remote format as legacy `POSITIONAL` and report unknown formats or inconsistent examples as actionable invalid state.
- [ ] 2.2 Preserve existing local `named_field_mapping` and `for_doctype` by variable identity during fetch/sync in `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py`; retain recoverable remote body/format/examples with stale bindings flagged for correction, and do not overwrite a prior valid local record when remote structure is unusable.
- [ ] 2.3 Extend `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/test_whatsapp_templates.py` with mocked fetch insert/update coverage for reordered variables, matching and inconsistent examples, missing/unsupported format, duplicate definitions, stale bindings, per-template diagnostics, and proof that import validation runs despite hook-free upsert.
- [ ] 2.4 Record the live Meta named-example and update-format verification outcome before rollout; a controlled non-production round-trip is required to establish API acceptance, and if unavailable or unsuccessful named creation/sending must remain unavailable rather than being reported as accepted.

## Phase 3: Outbound Message Serialization

- [ ] 3.1 Update `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py` to load the template's effective explicit format and prepare body parameters from parsed placeholder identities; named values include `parameter_name`, repeated occurrences reuse one value, and positional values follow numeric placeholder order.
- [ ] 3.2 Reject malformed JSON, unknown named identities, and absent or blank required named values before `notify()` or HTTP dispatch in `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py`; do not use `named_field_mapping` to resolve CRM/reference fields or treat examples as send defaults.
- [ ] 3.3 Extend `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/test_whatsapp_message.py` to cover named and repeated values, reversed positional input order, absent legacy format, pre-dispatch rejection, serialized `template_parameters`, and unchanged header/static/dynamic button behavior.

## Phase 4: Notification Boundary and Regression Verification

- [ ] 4.1 Reject explicit `NAMED` templates at the start of `send_simple_template()` and `send_template_message()` in `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_notification/whatsapp_notification.py`, before payload construction or dispatch; keep positional field-row handling unchanged, including scheduled routes that call these methods.
- [ ] 4.2 Extend `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_notification/test_whatsapp_notification.py` to assert named rejection with zero `notify()` calls for simple, dynamic, and scheduled routes, plus unchanged positional notification behavior.
- [ ] 4.3 Run focused template, message, and notification tests and the configured full app suite from an initialized bench; record unavailable infrastructure honestly. Do not treat mocked tests as proof of Meta acceptance, and keep production named-template enablement blocked until the live API prerequisite is satisfied.

## Key Learnings

1. Frappe's hook-free `upsert_doc_without_hooks()` requires remote template validation to run explicitly before import persistence.
2. The planned implementation crosses template storage, synchronization, message sending, and a separate notification sender, so reviewable PR slices are appropriate above the 400-line budget.
3. Mocked payload tests can verify local contracts but cannot establish Meta API acceptance for named examples or update format.
