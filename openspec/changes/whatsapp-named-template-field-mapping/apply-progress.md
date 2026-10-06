# Apply Progress: Explicit WhatsApp Template Parameter Formats

## Change
`whatsapp-named-template-field-mapping`

## Mode and delivery
- Standard Mode (`strict_tdd: false`), per `openspec/config.yaml`.
- Stacked-to-main was selected. Planned boundaries remain Work Unit 1 (local template contract), Work Unit 2 (fetch/sync), and Work Unit 3 (message + notification).
- Only local app files were edited. No push, PR, live Meta API call, or production send was performed.

## Implementation state
Code for the following local tasks has been written and its focused Frappe test evidence was produced on 2026-10-06 (see Work Unit Evidence below):
- Work Unit 1: 1.1–1.4 — additive `parameter_format`, `named_field_mapping`, and `named_example_values`; shared explicit-format, placeholder and JSON validation; local create/update BODY construction; focused template tests.
- Work Unit 2: 2.1–2.3 — remote BODY format/example validation before hook-free upsert; preserve local doctype/mapping by variable identity; report invalid imports and skip unusable remote templates; mocked parser/fetch tests.
- Work Unit 3: 3.1–3.3, 4.1–4.2 — named/positional message parameter construction in explicit body order, pre-dispatch validation, notification named-template rejection, focused message/notification tests.
- 2.4 remains incomplete: no live Meta create/update/fetch round-trip was performed. That requires an explicitly authorized non-production destination/account/session and must establish actual named-example and update-format acceptance before production enablement.

## Work Unit Evidence
| Unit | Focused test command and result | Runtime harness | Rollback boundary |
|---|---|---|---|
| 1 — local template contract | `bench --site sipra.localhost run-tests --module frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.test_whatsapp_templates` — Ran 21, OK (2026-10-06 local podman bench). | N/A for local payload construction; mocked Meta-request assertions executed. No live Meta claim. | Revert the template DocType JSON, template controller, and template tests together; retain additive field values. |
| 2 — fetch/sync | Same template module run — 21 OK covers mocked fetch/import validation and binding preservation. | Controlled non-production Meta fetch still not run; task 2.4 remains a pre-rollout prerequisite. | Revert fetch/import changes in the template controller and corresponding template tests; preserve stored mapping/example fields. |
| 3 — message/notification | `...whatsapp_message.test_whatsapp_message` — Ran 18, OK; `...whatsapp_notification.test_whatsapp_notification` — Ran 16, OK. Full app suite `run-tests --app frappe_whatsapp` — 137+15 OK after unrelated bulk `message_type` fix (`aa86f4b`). | N/A for live dispatch; local tests mock notify/HTTP. No live send or remote operation was authorized. | Revert message and notification controllers and their tests together; suspend named sends on the prior code while retaining template metadata. |

## Verification

Initial host attempts (2026-09-28): `python -m py_compile`, JSON parse, and `git diff --check` passed; no `bench`/`docker` executable was available, so no Frappe tests could run and all task IDs stayed unchecked.

Bench verification (2026-10-06, local podman harness `crm-sipra-local_frappe_1`, site `sipra.localhost`, Frappe 16; app installed editable and migrated):
- `bench --site sipra.localhost run-tests --module frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_templates.test_whatsapp_templates` — Ran 21 tests, OK.
- `bench --site sipra.localhost run-tests --module frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_message.test_whatsapp_message` — Ran 18 tests, OK.
- `bench --site sipra.localhost run-tests --module frappe_whatsapp.frappe_whatsapp.doctype.whatsapp_notification.test_whatsapp_notification` — Ran 16 tests, OK.
- `bench --site sipra.localhost run-tests --app frappe_whatsapp` — first run: Ran 137 tests, FAILED (failures=1). The single failure was pre-existing and unrelated to this change: `bulk_whatsapp_message.create_single_message()` set `message_type = "Text"`, which is not a valid Select option (`Manual`/`Template`), and the `except Exception` swallowed the ValidationError. Fixed on branch `fix/bulk-message-type-manual` (commit `aa86f4b`, PR pending). Re-run after the fix: Ran 137 tests OK plus Ran 15 flow tests OK, exit 0.
- These are mocked/local contract proofs. No live Meta API request was performed; task 2.4 remains unsatisfied by these runs.

## Tasks and next steps
- Tasks 1.1–1.4, 2.1–2.3, 3.1–3.3, 4.1–4.3 are checked as verified by the 2026-10-06 bench runs above.
- Task 2.4 remains pending until a non-production Meta round-trip is explicitly authorized and its response/request behavior is observed; mocks do not satisfy it.
- Next: open and merge the `fix/bulk-message-type-manual` PR, then complete 2.4 under explicit authorization before production named-template enablement.
