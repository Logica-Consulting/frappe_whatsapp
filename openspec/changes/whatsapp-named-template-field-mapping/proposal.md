# Proposal: Explicit WhatsApp Template Parameter Formats

## Intent

Allow this app to store, synchronize, and send Meta WhatsApp templates with named body parameters without breaking existing positional templates. Today template metadata retains only comma-separated positional values, sync imports only positional examples, and outbound sends infer format from placeholder text instead of persisted Meta format.

## Scope

### In Scope
- Add `parameter_format` and `named_field_mapping` (`{variable_name: fieldname}` JSON) to WhatsApp Templates. An absent legacy format behaves as `POSITIONAL`; retain `for_doctype`, `field_names`, and `sample_values`.
- Preserve explicit `NAMED`/`POSITIONAL` and the corresponding body example shape during template create, update, fetch, and sync. Sync retains local mappings by variable name rather than silently reindexing them.
- Build format-correct WhatsApp Message body parameters: named sends include `parameter_name`; positional sends follow placeholder order. Reject incomplete named values before HTTP dispatch; preserve header and button behavior.
- Add focused app tests for format persistence, Meta payloads, sync preservation, legacy compatibility, ordering, and pre-dispatch rejection.

### Out of Scope
- CRM APIs, CRM UI, CRM source edits, and CRM record-value resolution or per-send field-mapping UI; those belong to a separate change/repository.
- Changing the separate WhatsApp Notification positional field-row send path. Named-template notification delivery is **not supported by this proposal** and requires an explicit follow-up decision before it can be claimed supported.

## Capabilities

### New Capabilities
- `whatsapp-template-parameters`: Persisted body parameter format, name-keyed bindings, format-correct Meta examples and outbound parameters, and legacy positional compatibility.

### Modified Capabilities
None; `openspec/specs/` currently contains no capability specs.

## Approach

Use persisted `parameter_format` as the sole format authority, with an effective `POSITIONAL` default for existing records. Keep named bindings keyed by variable name and validate their completeness against the named template body. Build Meta body examples and outbound body parameters separately for each format; sync reads the explicit remote format and matching example shape while preserving existing local bindings by name. Do not infer format from `{{...}}`. Keep existing header/button handling and the independent notification caller unchanged. The expected Meta named-example structure is based on supplied planning evidence, not a live Meta round-trip; verify it during implementation.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.json` | Modified | Add persisted format and JSON mapping fields. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py` | Modified | Validate fields; create, update, fetch, and sync format-specific body examples without remapping bindings. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/whatsapp_message.py` | Modified | Construct and validate format-correct body parameters before dispatch. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_templates/test_whatsapp_templates.py` | Modified | Test template payload and sync behavior. |
| `frappe_whatsapp/frappe_whatsapp/doctype/whatsapp_message/test_whatsapp_message.py` | Modified | Test named, positional, legacy, and rejection behavior. |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `fetch()` bypasses hooks, so imported data may skip validation. | High | Explicitly normalize/validate remote format and examples in sync; test both shapes and missing format. |
| Existing positional callers depend on legacy fields or object ordering. | Medium | Keep legacy fields, derive positional order from placeholders, and test existing send paths. |
| Notification sends positional fields through a separate caller. | Medium | Leave it unchanged and do not claim named-template support there; decide separately whether to guard that use. |
| Supplied Meta named-example contract differs from live API behavior. | Medium | Validate against Meta documentation or a controlled API round-trip before deployment; do not treat mocks as live proof. |

## Rollback Plan

Revert the app code/DocType changes and redeploy the prior version. Leave additive stored fields in place rather than deleting user mappings; existing positional fields remain available, while named-template sends must be suspended until the corrected version is restored.

## Dependencies

- An initialized Frappe bench with MariaDB and Redis for app tests; a Meta API verification path is needed before a production delivery claim.

## Success Criteria

- [ ] Legacy templates with no stored format create, sync, and send as positional without data migration.
- [ ] Named and positional create/update/fetch/sync payload tests preserve explicit format, matching example structure, and name-keyed mappings across reorder.
- [ ] Outbound tests assert named `parameter_name`, positional placeholder order, and rejection of incomplete named values before `notify()`/HTTP.
- [ ] Existing header/button and positional notification behavior remains unchanged; app test suite passes in an initialized bench.
