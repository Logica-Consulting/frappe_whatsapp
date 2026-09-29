# Apply Progress: Explicit WhatsApp Template Parameter Formats

## Change
`whatsapp-named-template-field-mapping`

## Mode and delivery
- Standard Mode (`strict_tdd: false`), per `openspec/config.yaml`.
- Stacked-to-main was selected. Planned boundaries remain Work Unit 1 (local template contract), Work Unit 2 (fetch/sync), and Work Unit 3 (message + notification).
- Only local app files were edited. No push, PR, live Meta API call, or production send was performed.

## Implementation state
Code for the following local tasks has been written, but their unit task IDs remain unchecked until the focused Frappe tests can run and produce evidence:
- Work Unit 1: 1.1–1.4 — additive `parameter_format`, `named_field_mapping`, and `named_example_values`; shared explicit-format, placeholder and JSON validation; local create/update BODY construction; focused template tests.
- Work Unit 2: 2.1–2.3 — remote BODY format/example validation before hook-free upsert; preserve local doctype/mapping by variable identity; report invalid imports and skip unusable remote templates; mocked parser/fetch tests.
- Work Unit 3: 3.1–3.3, 4.1–4.2 — named/positional message parameter construction in explicit body order, pre-dispatch validation, notification named-template rejection, focused message/notification tests.
- 2.4 remains incomplete: no live Meta create/update/fetch round-trip was performed. That requires an explicitly authorized non-production destination/account/session and must establish actual named-example and update-format acceptance before production enablement.

## Work Unit Evidence
| Unit | Focused test command and result | Runtime harness | Rollback boundary |
|---|---|---|---|
| 1 — local template contract | `bench --site test_site run-tests --doctype "WhatsApp Templates"` — unable to start; PowerShell reports `bench` is not recognized. No test count/result is available. | N/A for local payload construction; mocked Meta-request assertions are present but were not executed. No live Meta claim. | Revert the template DocType JSON, template controller, and template tests together; retain additive field values. |
| 2 — fetch/sync | `bench --site test_site run-tests --doctype "WhatsApp Templates"` — unable to start for the same missing executable; no test count/result is available. | Controlled non-production Meta fetch was not run; it is not authorized by the provided destination/account/session scope. Remains a pre-rollout prerequisite. | Revert fetch/import changes in the template controller and corresponding template tests; preserve stored mapping/example fields. |
| 3 — message/notification | `bench --site test_site run-tests --doctype "WhatsApp Message"` and `bench --site test_site run-tests --doctype "WhatsApp Notification"` — both unable to start; PowerShell reports `bench` is not recognized. No test count/result is available. | N/A for live dispatch; local tests mock notify/HTTP. No live send or remote operation was authorized. | Revert message and notification controllers and their tests together; suspend named sends on the prior code while retaining template metadata. |

## Verification
- `python -m py_compile` on all six changed Python source/test files — PASS.
- Python JSON parse of `whatsapp_templates.json` — PASS.
- `git diff --check` — PASS (Git emitted LF-to-CRLF working-copy warnings only).
- `bench --site test_site run-tests --doctype "WhatsApp Templates"` — unable to start (`bench` not recognized).
- `bench --site test_site run-tests --doctype "WhatsApp Message"` — unable to start (`bench` not recognized).
- `bench --site test_site run-tests --doctype "WhatsApp Notification"` — unable to start (`bench` not recognized).
- `bench --site test_site run-tests --app frappe_whatsapp` — unable to start (`bench` not recognized).
- Bounded local Docker fallback check — unavailable; host does not recognize `docker`, so no existing bench container could be inspected or used. No container/service was started or changed.
- No work-unit commits were created: none has the required focused Frappe test evidence. No commit hashes exist for this apply batch.

## Tasks and next steps
- Tasks 1.1–1.4, 2.1–2.3, 3.1–3.3, 4.1–4.2 remain unchecked pending focused Frappe test execution and observed results.
- Task 2.4 remains pending until a non-production Meta round-trip is explicitly authorized and its response/request behavior is observed; mocks do not satisfy it.
- Task 4.3 records the four required command attempts and their unavailable result; no suite pass is claimed.
- Next: run all focused and full tests in an initialized bench. Fix any failures, then close and commit each verified work unit separately using Conventional Commit messages. Do not stage `.atl/` or unrelated OpenSpec initialization assets.
