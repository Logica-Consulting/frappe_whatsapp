# Design: Explicit WhatsApp Template Parameter Formats

## Technical Approach

Make `WhatsApp Templates.parameter_format` the sole body-format authority, with an effective `POSITIONAL` value for empty legacy records. Keep a name-keyed JSON field mapping and a separate name-keyed JSON example store; the existing comma-separated positional fields remain untouched. Reuse one body-format/placeholder validation and serialization contract in the template controller and message sender. Import from Meta explicitly validates before the existing hook-free upsert, preserves local bindings by variable name, and reports invalid imports without silently reindexing them. The separate `WhatsApp Notification` path remains positional-only and rejects named templates before it calls `notify()`.

This implements `specs/whatsapp-template-parameters/spec.md` within this app. CRM field-value resolution and CRM UI are excluded. The exact Meta named-example contract remains a verification prerequisite, not a proven API behavior.

## Architecture Decisions

### Decision: Persist format, mappings, and named examples separately

**Choice**: Add `parameter_format` (`Select`, options `POSITIONAL`/`NAMED`, default `POSITIONAL`), `named_field_mapping` (`Code`, JSON object), and `named_example_values` (`Code`, JSON object) to `WhatsApp Templates`. Read empty `parameter_format` as positional without writing it back. The mapping's values are field names scoped by the same record's `for_doctype`; examples' values are example text, not field names.

**Alternatives considered**: Infer format from placeholder text; encode named examples in `sample_values`; use JSON object order as a variable index.

**Rationale**: Explicit format survives ambiguous placeholder text and remote synchronization. A third field is necessary: the proposed two new fields have no place to persist name-associated examples without repurposing legacy `sample_values` or confusing field names with examples. This is an additive schema detail within the specified example-persistence scope. Existing `for_doctype`, `field_names`, and `sample_values` retain their original meaning and contents.

### Decision: Parse identities once, order from the body, reject ambiguity

**Choice**: Introduce small controller-level helpers for effective format, JSON-object parsing, placeholder extraction, and validation; import them from the message and notification controllers rather than duplicating inference. For `NAMED`, extract unique identifiers in first-occurrence order, require the supported identifier grammar, and reject malformed placeholders, duplicate mapping/example definitions, stale example/mapping keys, and missing required examples. Repeated `{{variable}}` occurrences in one body refer to one identity and reuse one mapping, example, and send value; rendering substitutes that value at every occurrence. For `POSITIONAL`, extract numeric placeholder indexes and serialize in numeric placeholder order; validate duplicate/gapped/unknown indexes rather than trusting dictionary iteration. A body with zero placeholders yields zero body parameters.

**Alternatives considered**: Keep `_detect_named_format()` in `WhatsApp Message`; iterate `body_param.items()`; infer positional order from `field_names` or `sample_values` alone.

**Rationale**: The current sender infers format from regex and positional sends use incidental JSON iteration order. A shared explicit parser prevents the template payload and send payload from disagreeing. Validation errors name the offending variable/index. Existing positional field-row values still come from legacy fields, but are aligned to the parsed positional placeholder order. If legacy field names cannot be aligned unambiguously, reject rather than risk a mis-send.

### Decision: Validate local writes before Meta I/O; validate import before hook-free persistence

**Choice**: Run local body/JSON/mapping validation at the beginning of `WhatsAppTemplates.validate()`, before its existing `update_template()` call. `after_insert()` and `update_template()` use one body-component builder: explicit format plus `body_text_named_params` (`param_name`, `example`) for named templates, and existing `body_text` for positional templates. Keep existing header, footer, and button construction unchanged. In `fetch()`, parse and validate each remote template's top-level format and matching BODY example before `upsert_doc_without_hooks()`, because that upsert calls `db_insert`/`db_update` and never runs `validate()`. Preserve prior local `named_field_mapping` and `for_doctype` by name, never by array position. Report specific invalid remote format/example/duplicate/stale-binding conditions per template in the fetch result and error log. Store recoverable remote body/format/examples while retaining stale local bindings for correction; do not emit a generic success for invalid imports. A structurally unusable remote template must not overwrite a previously valid local record.

**Alternatives considered**: Call `doc.save()` from fetch; clear stale bindings; abort an entire account import on the first invalid template.

**Rationale**: `save()` would trigger `validate()` and therefore the remote `update_template()` API call during sync. Clearing or reindexing bindings would silently lose user configuration. Per-template diagnostics allow other templates to synchronize while making invalid state actionable. Existing account/template identity and button-child upsert remain intact.

### Decision: Resolve only values already supplied to the message path

**Choice**: Build outbound body parameters after loading the template but before assembling header/buttons or invoking `notify()`. For `body_param`, require a JSON object keyed by named identity or positional index; for named templates, require all body variables to have non-empty supplied values and reject unknown keys. For positional templates, index supplied values by parsed numeric placeholders, not JSON order. For existing `custom_ref_doc` and reference-document branches, retain the current caller-provided values/legacy lookup contract, but do not interpret `named_field_mapping` as an instruction to fetch CRM or reference fields. If a named send reaches a branch without a complete name-keyed value set, fail before dispatch. Serialize `self.template_parameters` in the same body order used for the outbound payload; it remains a JSON array for compatibility.

**Alternatives considered**: Resolve `named_field_mapping` against a reference record in this change; silently fill missing values with examples; send partial named parameters.

**Rationale**: The specification covers serialization, not source-of-value resolution. Examples are approval metadata, not send-time defaults. Failing before `notify()` prevents malformed named payloads from reaching HTTP while leaving header/button code unchanged. Existing positional paths remain supported.

### Decision: Guard every independent notification entry point

**Choice**: Reject explicit `NAMED` at the start of both `send_simple_template()` and `send_template_message()` before constructing or dispatching a payload. `send_scheduled_message()` reaches those methods, so its two routes inherit the guard. Leave positional field-row serialization and header/button handling unchanged.

**Alternatives considered**: Route notifications through `WhatsAppMessage.send_template()`; add `parameter_name` to notification rows.

**Rationale**: Notification is a separate sender with its own positional field rows. Supporting named values there would be new value-resolution behavior beyond this capability; silently treating named templates as positional would mis-send.

## Data Flow

```text
Local create/update
  DocType fields -> format/body/JSON validation -> BODY example builder
       -> existing header/footer/button builder -> Meta request

Meta fetch
  remote format + BODY example -> explicit import validator
       -> preserve local mapping by variable name -> hook-free upsert
       -> per-template invalid-state diagnostics (when needed)

WhatsApp Message
  stored effective format + ordered placeholders + supplied body_param
       -> complete parameters / actionable rejection -> existing header/buttons
       -> notify() -> HTTP

WhatsApp Notification
  stored effective format -> NAMED rejection or unchanged positional rows
       -> notify() -> HTTP
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.json` | Modify | Add format, named mapping, and named example JSON fields; retain legacy fields. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py` | Modify | Shared format/placeholder/JSON validation; format-specific create/update BODY payloads; explicit fetch parsing, name-keyed preservation, and diagnostics before hook-free upsert. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py` | Modify | Replace placeholder inference and object-order serialization with explicit-format body parameter preparation and pre-dispatch validation. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_notification/whatsapp_notification.py` | Modify | Reject named templates in both independent send methods; retain positional logic. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/test_whatsapp_templates.py` | Modify | Focused local payload, validation, import, preservation, and legacy tests using existing `IntegrationTestCase` and mocked Meta request helpers. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/test_whatsapp_message.py` | Modify | Named/positional ordering, missing-value rejection before `notify()`/HTTP, legacy, header/button regression tests. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_notification/test_whatsapp_notification.py` | Modify | Positional regression and named rejection for simple, dynamic, and scheduled entry points. |

## Interfaces / Contracts

Stored template shape (illustrative; JSON objects are serialized as text in DocType fields):

```json
{
  "parameter_format": "NAMED",
  "for_doctype": "Sales Order",
  "named_field_mapping": "{\"first_name\":\"customer_name\",\"order_id\":\"name\"}",
  "named_example_values": "{\"first_name\":\"Ada\",\"order_id\":\"SO-001\"}"
}
```

The parser returns a deterministic list of unique identities from the BODY text in first-occurrence order; repeated occurrences are not duplicate definitions and do not create extra mapping, example, or outbound parameter entries. Rendering uses the same identity value at every occurrence. JSON decoding requires an object and string keys; malformed JSON, duplicate JSON keys, duplicate named-example entries, unsupported format values, stale keys, and missing required examples are explicit errors. Duplicate JSON keys must be detected with an `object_pairs_hook` or equivalent, because ordinary `json.loads()` silently keeps the last value. The named mapping may be empty when no doctype binding is needed; completeness is checked for a use that requires field mapping, not invented at send-time. Once supplied values are present, mapping metadata is not used to resolve them. An explicit change of `for_doctype` with an existing mapping requires revalidation rather than interpreting the old mapping against the new DocType.

Expected Meta body component, subject to the live verification prerequisite:

```json
{
  "type": "BODY",
  "text": "Hello {{first_name}}, order {{order_id}} is ready for {{first_name}}",
  "example": {
    "body_text_named_params": [
      {"param_name": "first_name", "example": "Ada"},
      {"param_name": "order_id", "example": "SO-001"}
    ]
  }
}
```

Create includes the explicit top-level `parameter_format`; update sends the format only if the endpoint supports it (verify before rollout). Fetch reads the remote top-level `parameter_format`, treating absence as legacy positional but never coercing an unknown value. If named examples are absent/inconsistent, report the exact template and variable; do not synthesize examples from positional data. Positional payloads retain `example.body_text: [[...]]`.

Outbound named body parameter example:

```json
{"type": "text", "parameter_name": "first_name", "text": "Ada"}
```

The outbound list follows first-occurrence order of unique named variables and numeric placeholder order for positional variables. A repeated named placeholder reuses one supplied value and produces one named parameter, while every rendered occurrence receives that value. JSON text order is never an authority. Missing or blank required named values, unknown supplied identities, malformed JSON, and unsupported format reject before `notify()`; a missing named mapping alone does not cause implicit record lookup. Header and button components are appended by the existing logic after body preparation.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Controller/contract | Effective legacy positional format; explicit format over placeholder appearance; repeated named occurrences collapse to one first-occurrence identity; duplicate mapping/example keys and malformed/stale keys; named example parsing/ordering; positional placeholder ordering | Focused `IntegrationTestCase` methods using Frappe fixtures and pure helper assertions. |
| Template integration | Create/update request JSON, one named example for repeated body occurrences, format and matching example shape, unchanged header/buttons; fetch insert/update, reorder preservation, duplicate named-example definition rejection, missing/unsupported format, inconsistent examples, invalid-state diagnostics | Mock `make_post_request`/`make_request`; inspect stored DocType fields and captured JSON. Verify import directly because `upsert_doc_without_hooks()` skips hooks. |
| Message integration | One named `parameter_name` and reused value for repeated occurrences, positional index order despite reversed input object, absent legacy format, complete-value checks, unchanged header/static/dynamic button behavior | Mock `notify()` or `make_post_request`; assert malformed named values never call either and valid payloads retain existing components. |
| Notification integration | Existing positional field rows, named rejection for simple/dynamic/scheduled routes | Extend current notification tests; mock `notify()` and assert zero calls for named templates. |
| Live Meta acceptance | Real create/update/fetch/send shape and response, particularly named example keys and format on update | Controlled non-production Meta account/template round-trip after local tests; mocks cannot establish this proof. |

Run focused tests from an initialized bench and site (MariaDB and Redis running), for example `bench --site test_site run-tests --doctype "WhatsApp Templates"`, `bench --site test_site run-tests --doctype "WhatsApp Message"`, and `bench --site test_site run-tests --doctype "WhatsApp Notification"`; run the configured full suite with `bench --site test_site run-tests --app frappe_whatsapp`. CI provisions a bench/site and runs this full suite. These commands are not runnable as standalone Python tests from this repository checkout.

## Threat Matrix

N/A — this design changes DocType metadata, Meta payload construction, import validation, and send validation only. It does not change routing, shell commands, subprocesses, VCS/PR automation, executable-file classification, or process integration; therefore no listed threat-matrix boundary or corresponding RED test applies.

## Migration / Rollout

No data migration required. New fields are additive; empty pre-existing `parameter_format` reads as positional without writeback. Deploy schema and code together, then run the bench tests. Before enabling named templates in production, verify the supplied `body_text_named_params`/`param_name`/`example` schema and top-level/update `parameter_format` behavior against current Meta documentation or a controlled live round-trip. If verification fails, keep named creation/sending unavailable rather than treating mocked tests as API acceptance. Rollback reverts code/schema behavior without deleting stored named mappings or examples; suspend named sends on the prior code version.

## Open Questions

- [ ] Confirm current Meta Cloud API acceptance and fetch representation for `parameter_format`, `body_text_named_params`, `param_name`, and `example`, including whether the update endpoint accepts `parameter_format`. This was supplied as planning context, not live-verified.
- [ ] Confirm whether any existing callers supply positional `body_param` keys that are not placeholder numbers; if so, define an explicit compatibility adapter based on existing `field_names` without restoring object-order dependence.
- [ ] Confirm the desired user-facing invalid-import reporting surface: structured fetch result plus Frappe error log is proposed; any existing UI consumer expecting the exact success string should be checked before changing that response.
- [ ] Obtain user approval for the proposed additive `named_example_values` field before implementation; it is needed to preserve name-associated examples without repurposing legacy `sample_values`.
