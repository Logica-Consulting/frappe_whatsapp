# whatsapp-template-parameters Specification

## Purpose

Define how WhatsApp Templates represent and synchronize explicit body-parameter formats, preserve named-variable mappings, and serialize body parameters for outbound WhatsApp Messages while retaining legacy positional behavior.

## Requirements

### Requirement: Explicit parameter format with positional legacy compatibility

A WhatsApp Template MUST persist an explicit body parameter format of `NAMED` or `POSITIONAL`. A record with an absent format MUST be treated as `POSITIONAL` without requiring migration or rewriting of the record. The system MUST NOT infer the parameter format from placeholder text. Existing `for_doctype`, `field_names`, and `sample_values` MUST remain available for positional templates, and enabling this capability MUST NOT automatically migrate existing template data.

#### Scenario: Legacy record without a format is positional

- GIVEN a stored WhatsApp Template has no `parameter_format` value and has legacy positional fields
- WHEN the template is fetched, synchronized, or used to send a message
- THEN the effective format is `POSITIONAL`
- AND its legacy positional fields remain available
- AND the record is not automatically rewritten or migrated

#### Scenario: Explicit format wins over placeholder appearance

- GIVEN a WhatsApp Template explicitly stores `POSITIONAL` or `NAMED`
- WHEN its body text contains placeholders that could otherwise suggest another format
- THEN the stored format determines the example and outbound parameter format
- AND the system does not infer or silently change the format from placeholder text

#### Scenario: Unsupported or absent remote format during synchronization

- GIVEN a remote template omits its parameter format
- WHEN the remote template is synchronized
- THEN it is treated as `POSITIONAL`
- AND if a remote template supplies a value other than `NAMED` or `POSITIONAL`, synchronization records an actionable invalid state rather than silently treating it as another format

### Requirement: Name-keyed mappings are scoped to the template doctype

A WhatsApp Template MAY persist a mapping from each named body variable to a field name. Each mapping MUST be scoped to that template's `for_doctype`; it MUST NOT be interpreted as a global mapping. The named mapping MUST coexist with the legacy positional `field_names` and `sample_values`, which MUST NOT be discarded or repurposed when a template is named. Each distinct named variable identity MUST have exactly one mapping and one example, regardless of how many times that variable occurs in the body. Repeated occurrences of the same `{{variable}}` are one logical variable, not duplicate definitions. Duplicate mapping keys, duplicate named example entries, stale mapping keys, and missing required mappings MUST be surfaced as actionable invalid template state; the system MUST NOT silently remap them.

#### Scenario: Mapping remains tied to its template doctype

- GIVEN a named WhatsApp Template has `for_doctype` set and stores a variable-to-field mapping
- WHEN the mapping is read or used as template metadata
- THEN it remains associated with that template and its `for_doctype`
- AND it is not treated as a mapping for another doctype

#### Scenario: Legacy positional fields survive named-format configuration

- GIVEN a WhatsApp Template has existing `field_names` and `sample_values`
- WHEN a named mapping is stored for that template
- THEN the named mapping is retained separately
- AND the existing positional fields remain unchanged and available for positional compatibility

#### Scenario: Repeated occurrences share one logical variable

- GIVEN a named template body contains `{{first_name}}` more than once
- WHEN its variable definitions are validated
- THEN all occurrences are treated as one logical variable identity, `first_name`
- AND one mapping and one named example are sufficient for that identity

#### Scenario: Duplicate mapping keys or named examples are invalid

- GIVEN a named template contains more than one mapping entry or named example entry for the same variable identity, including duplicate keys in serialized mapping data
- WHEN the template is validated or synchronized
- THEN the template is reported as invalid with an actionable indication of the duplicate mapping or example
- AND no mapping or example is silently selected or reassigned

#### Scenario: Stale mapping key is invalid

- GIVEN a named mapping contains a variable key that is not defined by the current template body
- WHEN the template is updated or synchronized
- THEN the stale mapping is reported as actionable invalid state
- AND the mapping is not silently reassigned to a different variable

#### Scenario: Missing mapping is actionable

- GIVEN a named template contains a variable with no corresponding mapping
- WHEN the template is validated for a use that requires a complete mapping
- THEN validation identifies the missing variable as actionable invalid state
- AND the system does not silently substitute another field or positional value

### Requirement: Create, update, fetch, and synchronization preserve explicit format and matching examples

Template create, update, fetch, and synchronization MUST preserve the explicit `NAMED` or `POSITIONAL` format and use the corresponding body-example shape. For named format, the supplied Meta schema basis is `body_text_named_params` entries containing `param_name` and `example`. For positional format, the supplied Meta schema basis is the existing `body_text` example shape. Synchronization MUST retain existing local named mappings by variable identity when the remote template changes or reorders variables; it MUST NOT silently remap by position. Missing or inconsistent remote format or examples MUST produce an actionable invalid state, except that an absent format is handled as legacy `POSITIONAL` as specified above.

The named-example structure in this specification is based on supplied planning evidence and has not been verified through a live Meta API round-trip. Passing mocked tests or local validation MUST NOT be represented as proof of Meta delivery or live API acceptance.

#### Scenario: Named create and update use named examples

- GIVEN a WhatsApp Template is explicitly `NAMED` and has named body variables with example values
- WHEN the template is created or updated with Meta
- THEN its body example uses `body_text_named_params`
- AND each named example entry identifies its variable with `param_name` and supplies its example with `example`
- AND the operation preserves the explicit `NAMED` format

#### Scenario: Positional create and update use positional examples

- GIVEN a WhatsApp Template is `POSITIONAL`, including one whose legacy format is absent
- WHEN the template is created or updated with Meta
- THEN its body example uses the existing positional `body_text` shape
- AND its values correspond to the positional placeholders in their defined order

#### Scenario: Fetch retains named format and mapping

- GIVEN a fetched remote template explicitly identifies named format and provides a valid named example
- WHEN the template is stored locally
- THEN its local format is `NAMED`
- AND the named example is associated with its variable identity
- AND existing local mappings for matching variable identities are retained

#### Scenario: Synchronization preserves mappings across variable reorder

- GIVEN a local named template maps variables `first_name` and `order_id` to fields
- AND the synchronized remote template contains the same variable identities in a different order
- WHEN synchronization updates the local template
- THEN mappings remain associated with their original variable identities
- AND no mapping is reassigned merely because its variable moved to another position

#### Scenario: Synchronization reports a changed or inconsistent variable set

- GIVEN synchronization finds duplicate variables, stale local mapping keys, missing required definitions, or an example shape inconsistent with the explicit remote format
- WHEN synchronization processes the template
- THEN it reports the specific invalid condition as actionable state
- AND it does not silently change the format or remap local bindings

### Requirement: Outbound body parameters follow the explicit format

When an outbound WhatsApp Message includes body parameter values, it MUST serialize them according to the template's effective explicit format. Named body parameters MUST include `parameter_name` for the corresponding variable identity. Positional body parameters MUST follow the body placeholder order, not incidental object or input-field iteration order. A named send with incomplete required values MUST be rejected before notification dispatch or HTTP dispatch. Existing header and button parameter behavior MUST be preserved. This requirement governs parameter serialization and validation only; it does not define how values are resolved from CRM or reference records.

#### Scenario: Named outbound parameters carry variable names

- GIVEN a valid named template and complete body values associated with its named variables
- WHEN a WhatsApp Message is prepared for outbound dispatch
- THEN each body parameter includes the matching `parameter_name`
- AND each value remains associated with the same variable identity
#### Scenario: Repeated named placeholder uses one parameter and replaces every occurrence

- GIVEN a named template body contains `Hello {{first_name}}, welcome {{first_name}}`
- AND one complete value is supplied for the logical variable `first_name`
- WHEN the WhatsApp Message is prepared for outbound dispatch
- THEN the body parameters contain one entry with `parameter_name` `first_name`
- AND that value is substituted at every occurrence of `{{first_name}}` in the body

#### Scenario: Positional outbound parameters follow placeholder order

- GIVEN a positional template whose body has multiple placeholders in a defined order
- AND supplied positional values arrive in a different object or field-row iteration order
- WHEN a WhatsApp Message is prepared for outbound dispatch
- THEN body parameters are serialized in placeholder order
- AND the effective format remains `POSITIONAL`

#### Scenario: Incomplete named values are rejected before dispatch

- GIVEN a named template requires values for multiple named variables
- AND at least one required value is absent
- WHEN the message is prepared for sending
- THEN it is rejected with an actionable missing-value indication
- AND neither notification dispatch nor HTTP dispatch is invoked

#### Scenario: Existing header and button parameters remain intact

- GIVEN a template message contains header or button parameters in addition to body parameters
- WHEN body parameters are serialized according to their explicit format
- THEN existing header and button parameter behavior is preserved
- AND body-format handling does not convert, drop, or reorder those parameters

### Requirement: Separate WhatsApp Notification path remains positional-only

The separate WhatsApp Notification template-send path is not supported for `NAMED` templates by this capability. Its existing positional behavior MUST remain unchanged. If a named-format template reaches this path, the system MUST reject it before dispatch with an actionable unsupported-format indication; it MUST NOT serialize it as positional or silently mis-send it.

#### Scenario: Positional notification behavior is preserved

- GIVEN a WhatsApp Notification uses a positional template
- WHEN its existing template-send path prepares the message
- THEN its existing positional field-row behavior is preserved

#### Scenario: Named template on notification path is rejected

- GIVEN a WhatsApp Notification attempts to use a template explicitly marked `NAMED`
- WHEN the separate notification path validates the template
- THEN it rejects the send before dispatch with an actionable unsupported-format indication
- AND it does not reinterpret the named template as positional

### Requirement: CRM value resolution and mapping UI are outside this capability

This capability MUST NOT define or imply CRM custom/reference-record field resolution, value lookup, or per-send field-mapping UI. It defines persisted template metadata, format-specific examples, validation boundaries, synchronization behavior, and outbound parameter serialization only. Any behavior that supplies CRM- or reference-record-derived values, or presents mapping controls in a CRM interface, requires a separate capability specification.

#### Scenario: Custom or reference-record value resolution is not specified here

- GIVEN an outbound request involves a custom or reference record
- WHEN this capability serializes body parameters
- THEN it does not define how values are looked up or resolved from that record
- AND no CRM value-resolution behavior is implied by the stored mapping

#### Scenario: CRM mapping UI is not part of the capability

- GIVEN a user configures a WhatsApp Template
- WHEN the capabilities specified here are implemented
- THEN this specification does not require or imply CRM-side mapping controls or per-send mapping UI
