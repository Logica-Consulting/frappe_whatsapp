## Exploration: WhatsApp named template field mapping

### Current State
`WhatsApp Templates` stores body text, comma-separated `sample_values` and `field_names`, and optional `for_doctype`, but no parameter format or name-keyed mapping. Create and update send positional `body_text` examples; `fetch()` imports only that example shape and bypasses validation/hooks through `upsert_doc_without_hooks`. Existing tests cover basic create/fetch and static-button behavior, not named format. `WhatsApp Message.send_template()` infers named format from body placeholder syntax, serializes `body_param` in JSON object iteration order for positional sends, and emits `parameter_name` only for named `body_param` values. Its custom/reference-document branches emit positional parameters regardless of detected format; it does not reject missing values before `notify()` dispatches HTTP. Bulk messaging feeds `body_param` or `flags.custom_ref_doc`; notification has a separate template-send path using positional field rows.

### Affected Areas
- `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.json` — persist explicit format and name-keyed bindings alongside legacy fields.
- `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py` — validate local template state, construct create/update body examples, and sync remote format/examples without reindexing bindings.
- `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/test_whatsapp_templates.py` — cover format, examples, validation, compatibility, and sync preservation.
- `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py` — construct and validate outbound body parameters by persisted format, preserving header/button logic.
- `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/test_whatsapp_message.py` — assert named keys, positional order, legacy null format, and pre-dispatch rejection.

### Approaches
1. **Explicit persisted format with keyed mapping** — add `parameter_format` and JSON `{variable_name: fieldname}` binding storage; use format-specific body example and send builders while retaining positional legacy fields.
   - Pros: matches the supplied Meta contract, survives sync/reordering, and keeps legacy rows compatible.
   - Cons: requires validation across create/update/sync/send and careful handling of existing send callers.
   - Effort: High

2. **Continue placeholder inference with a mapping overlay** — derive format from `{{...}}` and add optional keyed bindings only.
   - Pros: smaller schema and controller change.
   - Cons: cannot honor Meta's explicit format, cannot reliably preserve remote format, and retains ambiguous positional object ordering.
   - Effort: Medium

### Recommendation
Use explicit persisted format. Treat absent/legacy format as POSITIONAL; validate named identifiers, duplicate/stale mapping keys and complete send values before HTTP. For named templates, construct examples by variable name (`body_text_named_params` with `param_name`/`example`) and send parameters with `parameter_name`; preserve existing positional `body_text`, headers, and buttons. Sync should update body/format but retain name-keyed bindings for correction rather than silently remap them. Keep CRM metadata lookup and per-send UI outside this app-only change.

### Risks
- `fetch()` bypasses hooks, so import must explicitly normalize/validate remote format and examples; omitted remote format must remain positional.
- Existing positional sends rely on comma-separated fields or JSON object order; changing ordering needs tests against actual placeholder order and legacy data.
- `WhatsApp Notification` sends via a separate path that currently emits positional parameters; the proposal must identify whether named-template notification sending is excluded or needs an app-local guard.
- The supplied Meta payload details have not been verified against a live Meta response here; no delivery claim can follow from mocked tests.
- The nested app's `.atl/skill-registry.md` says it was generated without consulting the nested repository, so project-specific skill coverage is unverified.

### Ready for Proposal
Yes — propose only the `frappe_whatsapp` schema/controller/sync/outbound-message slice, with legacy positional compatibility and explicit tests. State notification and other caller behavior as a scoped compatibility boundary, and leave CRM record-derived resolution/UI for a separate repository change.
