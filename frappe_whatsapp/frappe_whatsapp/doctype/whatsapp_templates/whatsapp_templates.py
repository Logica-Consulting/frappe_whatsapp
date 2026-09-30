"""Create whatsapp template."""

# Copyright (c) 2022, Shridhar Patil and contributors
# For license information, please see license.txt
import json
import re
import frappe
import magic
import requests
from frappe.model.document import Document
from frappe.integrations.utils import make_post_request, make_request
from frappe.desk.form.utils import get_pdf_link

from frappe_whatsapp.utils import get_whatsapp_account


NAMED_PLACEHOLDER = re.compile(r"{{([A-Za-z][A-Za-z0-9_]*)}}")
POSITIONAL_PLACEHOLDER = re.compile(r"{{([1-9][0-9]*)}}")


def _json_object(value, label):
    """Decode an optional JSON object, preserving duplicate-key errors."""
    if not value:
        return {}

    def reject_duplicates(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                frappe.throw(f"{label} contains duplicate key '{key}'.")
            result[key] = item
        return result

    try:
        result = json.loads(value, object_pairs_hook=reject_duplicates)
    except (TypeError, json.JSONDecodeError) as exc:
        frappe.throw(f"{label} must contain valid JSON: {exc}")
    if not isinstance(result, dict) or not all(isinstance(key, str) for key in result):
        frappe.throw(f"{label} must be a JSON object with string keys.")
    return result


def effective_parameter_format(value):
    """Treat empty legacy formats as positional without mutating the record."""
    parameter_format = (value or "POSITIONAL").upper()
    if parameter_format not in ("POSITIONAL", "NAMED"):
        frappe.throw(f"Unsupported template parameter format '{value}'.")
    return parameter_format


def body_parameter_identities(body, parameter_format):
    """Return unique parameter identities in body order and reject malformed tokens."""
    parameter_format = effective_parameter_format(parameter_format)
    matcher = NAMED_PLACEHOLDER if parameter_format == "NAMED" else POSITIONAL_PLACEHOLDER
    identities = matcher.findall(body or "")
    residue = matcher.sub("", body or "")
    if "{{" in residue or "}}" in residue:
        frappe.throw(f"Template body contains a malformed {parameter_format.lower()} placeholder.")
    if parameter_format == "POSITIONAL":
        indexes = [int(index) for index in identities]
        unique = sorted(set(indexes))
        if unique and unique != list(range(1, max(unique) + 1)):
            frappe.throw("Positional placeholders must use contiguous indexes starting at {{1}}.")
        return [str(index) for index in unique]
    return list(dict.fromkeys(identities))


def validate_template_parameter_data(template):
    """Validate local format, placeholders, and name-keyed data before remote I/O."""
    parameter_format = effective_parameter_format(template.parameter_format)
    identities = body_parameter_identities(template.template, parameter_format)
    if parameter_format == "NAMED":
        mappings = _json_object(template.named_field_mapping, "Named field mapping")
        examples = _json_object(template.named_example_values, "Named example values")
        unknown_mappings = set(mappings) - set(identities)
        if unknown_mappings:
            frappe.throw("Named field mapping contains stale variable(s): " + ", ".join(sorted(unknown_mappings)))
        unknown_examples = set(examples) - set(identities)
        if unknown_examples:
            frappe.throw("Named example values contain stale variable(s): " + ", ".join(sorted(unknown_examples)))
        missing_examples = set(identities) - set(examples)
        if missing_examples:
            frappe.throw("Named example values are missing: " + ", ".join(name for name in identities if name in missing_examples))
        if any(not isinstance(value, str) for value in mappings.values()):
            frappe.throw("Named field mapping values must be strings.")
        if any(not isinstance(value, str) or not value.strip() for value in examples.values()):
            frappe.throw("Named example values must be non-empty strings.")
    elif template.sample_values:
        samples = template.sample_values.split(",")
        if len(samples) != len(identities):
            frappe.throw("Sample Values must provide one value for each positional placeholder.")
    return parameter_format, identities


def build_body_component(template):
    """Build BODY component using the template's explicit format and examples."""
    parameter_format, identities = validate_template_parameter_data(template)
    body = {"type": "BODY", "text": template.template}
    if parameter_format == "NAMED" and identities:
        examples = _json_object(template.named_example_values, "Named example values")
        body["example"] = {"body_text_named_params": [
            {"param_name": name, "example": examples[name]} for name in identities
        ]}
    elif parameter_format == "POSITIONAL" and template.sample_values:
        body["example"] = {"body_text": [template.sample_values.split(",")]}
    return body


def parse_remote_body(remote_template):
    """Validate the remote BODY component and return locally persistable values."""
    parameter_format = effective_parameter_format(remote_template.get("parameter_format"))
    body_components = [c for c in remote_template.get("components", []) if c.get("type") == "BODY"]
    if len(body_components) != 1:
        frappe.throw("Remote template must contain exactly one BODY component.")
    component = body_components[0]
    body_text = component.get("text")
    if not isinstance(body_text, str):
        frappe.throw("Remote BODY component is missing text.")
    identities = body_parameter_identities(body_text, parameter_format)
    example = component.get("example") or {}

    if parameter_format == "NAMED":
        entries = example.get("body_text_named_params")
        if not identities and not entries:
            named_examples = {}
        elif not isinstance(entries, list):
            frappe.throw("Remote named BODY example is missing body_text_named_params.")
        else:
            named_examples = {}
            for entry in entries:
                if not isinstance(entry, dict):
                    frappe.throw("Remote named BODY example entries must be objects.")
                name = entry.get("param_name")
                value = entry.get("example")
                if not isinstance(name, str) or not isinstance(value, str) or not value.strip():
                    frappe.throw("Remote named BODY examples require param_name and non-empty example values.")
                if name in named_examples:
                    frappe.throw(f"Remote named BODY example contains duplicate variable '{name}'.")
                named_examples[name] = value
            if set(named_examples) != set(identities):
                missing = [name for name in identities if name not in named_examples]
                stale = sorted(set(named_examples) - set(identities))
                details = []
                if missing:
                    details.append("missing: " + ", ".join(missing))
                if stale:
                    details.append("unexpected: " + ", ".join(stale))
                frappe.throw("Remote named BODY examples do not match placeholders (" + "; ".join(details) + ").")
        return parameter_format, body_text, "", json.dumps(named_examples, sort_keys=True)

    positional = example.get("body_text")
    if identities:
        if not isinstance(positional, list) or not positional or not isinstance(positional[0], list):
            frappe.throw("Remote positional BODY example is missing body_text values.")
        values = positional[0]
        if len(values) != len(identities) or any(not isinstance(value, str) for value in values):
            frappe.throw("Remote positional BODY example values do not match placeholder indexes.")
        sample_values = ",".join(values)
    else:
        sample_values = ",".join(positional[0]) if positional and isinstance(positional[0], list) else ""
    return parameter_format, body_text, sample_values, ""

class WhatsAppTemplates(Document):  # nosemgrep: frappe-modifying-but-not-committing-other-method -- get_settings() sets self._token/_url/_version/_business_id/_app_id/_headers as in-memory scratch for the outbound Meta HTTP call; they are not DocType fields and must not be persisted
    """Create whatsapp template."""

    def validate(self):
        validate_template_parameter_data(self)
        self.set_whatsapp_account()
        if not self.language_code or self.has_value_changed("language"):
            lang_code = frappe.db.get_value("Language", self.language) or "en"
            self.language_code = lang_code.replace("-", "_")

        if self.header_type in ["IMAGE", "DOCUMENT"] and self.sample:
            self.get_session_id(self.sample)
            self.get_media_id(self.sample)

        if not self.is_new() and self._requires_remote_sync():
            self.update_template()

    def _requires_remote_sync(self):
        """Return True if any changed field requires syncing with Meta."""
        remote_sync_fields = [
            "template", "header_type", "header", "footer", "language",
            "category", "status", "sample", "buttons"
        ]
        return any(self.has_value_changed(field) for field in remote_sync_fields)

    def set_whatsapp_account(self):
        """Set whatsapp account to default if missing"""
        if not self.whatsapp_account:
            default_whatsapp_account = get_whatsapp_account()
            if not default_whatsapp_account:
                throw(_("Please set a default outgoing WhatsApp Account or Select available WhatsApp Account"))
            else:
                self.whatsapp_account = default_whatsapp_account.name

    def get_session_id(self, file):
        """Upload media."""
        self.get_settings()

        # Check if it's a remote file, load data accordingly
        if file.startswith(('http://', 'https://')):
            remote_file_data = self._prepare_remote_file(file)
            file_type = remote_file_data['file_type']
            file_length = remote_file_data['file_size']
        else:
            file_content = self._read_local_file(file)
            mime = magic.Magic(mime=True)
            file_type = mime.from_buffer(file_content)
            file_length = len(file_content)

        payload = {
            'file_length': file_length,
            'file_type': file_type,
            'messaging_product': 'whatsapp'
        }

        response = make_post_request(
            f"{self._url}/{self._version}/{self._app_id}/uploads",
            headers=self._headers,
            data=json.loads(json.dumps(payload))
        )
        self._session_id = response['id']

    def _prepare_remote_file(self, file_url):
        """Download and return remote file content from URL."""
        try:
            response = requests.get(file_url, timeout=30)
            response.raise_for_status()
            
            file_content = response.content
            file_size = len(file_content)
            
            # Get MIME type from Content-Type header or detect from content
            content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
            if content_type:
                file_type = content_type
            else:
                # Fallback to magic detection from content
                mime = magic.Magic(mime=True)
                file_type = mime.from_buffer(file_content)
            
            return {
                'file_content': file_content,
                'file_size': file_size,
                'file_type': file_type
            }
        except Exception as e:
            frappe.throw(f"Failed to download file from URL: {str(e)}")

    def get_media_id(self, file):
        self.get_settings()

        headers = {
                "authorization": f"OAuth {self._token}"
            }
        
        # Check if it's a remote file, load data accordingly
        if file.startswith(('http://', 'https://')):
            remote_file_data = self._prepare_remote_file(file)
            file_content = remote_file_data['file_content']
        else:
            file_content = self._read_local_file(file)

        payload = file_content
        response = make_post_request(
            f"{self._url}/{self._version}/{self._session_id}",
            headers=headers,
            data=payload
        )

        self._media_id = response['h']

    def _read_local_file(self, file_url):
        # Routed through File so path resolution stays inside Frappe's
        # vetted file handling — never feed a raw URL to open().
        return frappe.get_doc("File", {"file_url": file_url}).get_content()


    def after_insert(self):  # nosemgrep: frappe-modifying-but-not-committing -- self.actual_name/id/status are persisted via self.db_update() after the Meta round-trip; the static check can't trace through the API call
        # actual_name / id / status are persisted via self.db_update() below
        # after the Meta round-trip; the static check can't trace that call.
        if self.template_name:
            self.actual_name = self.template_name.lower().replace(" ", "_")  # nosemgrep: frappe-modifying-but-not-committing

        self.get_settings()
        data = {
            "name": self.actual_name,
            "language": self.language_code,
            "category": self.category,
            "components": [],
        }

        data["parameter_format"] = effective_parameter_format(self.parameter_format)
        data["components"].append(build_body_component(self))
        if self.header_type:
            data["components"].append(self.get_header())

        # add footer
        if self.footer:
            data["components"].append({"type": "FOOTER", "text": self.footer})

        # add buttons
        if self.buttons:
            button_block = {"type": "BUTTONS", "buttons": []}
            for btn in self.buttons:
                b = {"type": btn.button_type, "text": btn.button_label}

                if btn.button_type == "Visit Website":
                    b["type"] = "URL"
                    b["url"] = btn.website_url
                    if btn.url_type == "Dynamic" and btn.example_url:
                        b["example"] = btn.example_url.split(",")
                elif btn.button_type == "Call Phone":
                    b["type"] = "PHONE_NUMBER"
                    b["phone_number"] = btn.phone_number
                elif btn.button_type == "Quick Reply":
                    b["type"] = "QUICK_REPLY"
                elif btn.button_type == "Multi-Product Message":
                    b["type"] = "MPM"
                elif btn.button_type == "Catalog":
                    b["type"] = "CATALOG"

                button_block["buttons"].append(b)

            data["components"].append(button_block)

        try:
            response = make_post_request(
                f"{self._url}/{self._version}/{self._business_id}/message_templates",
                headers=self._headers,
                data=json.dumps(data),
            )
            self.id = response["id"]  # nosemgrep: frappe-modifying-but-not-committing
            self.status = response["status"]  # nosemgrep: frappe-modifying-but-not-committing
            self.db_update()
        except Exception as e:
            res = frappe.flags.integration_request.json().get("error", {})
            error_message = res.get("error_user_msg", res.get("message"))
            frappe.throw(
                msg=error_message,
                title=res.get("error_user_title", "Error"),
            )

    def update_template(self):
        """Update template to meta."""
        self.get_settings()
        data = {"components": []}

        data["components"].append(build_body_component(self))
        if self.header_type:
            data["components"].append(self.get_header())
        if self.footer:
            data["components"].append({"type": "FOOTER", "text": self.footer})
        if self.buttons:
            button_block = {"type": "BUTTONS", "buttons": []}
            for btn in self.buttons:
                b = {"type": btn.button_type, "text": btn.button_label}

                if btn.button_type == "Visit Website":
                    b["type"] = "URL"
                    b["url"] = btn.website_url
                    if btn.url_type == "Dynamic" and btn.example_url:
                        b["example"] = btn.example_url.split(",")
                elif btn.button_type == "Call Phone":
                    b["type"] = "PHONE_NUMBER"
                    b["phone_number"] = btn.phone_number
                elif btn.button_type == "Quick Reply":
                    b["type"] = "QUICK_REPLY"
                elif btn.button_type == "Multi-Product Message":
                    b["type"] = "MPM"
                    # MPM buttons often require additional fields like catalog_id
                elif btn.button_type == "Catalog":
                    b["type"] = "CATALOG"

                button_block["buttons"].append(b)

            data["components"].append(button_block)

        try:
            # post template to meta for update
            make_post_request(
                f"{self._url}/{self._version}/{self.id}",
                headers=self._headers,
                data=json.dumps(data),
            )
        except Exception as e:
            raise e
            # res = frappe.flags.integration_request.json()['error']
            # frappe.throw(
            #     msg=res.get('error_user_msg', res.get("message")),
            #     title=res.get("error_user_title", "Error"),
            # )

    def get_settings(self):
        """Get whatsapp settings."""
        # Underscore-prefixed attributes below are in-memory scratch for the
        # outbound HTTP call — they are not DocType fields and must not be
        # persisted. Semgrep's static check can't tell the difference.
        settings = frappe.get_doc("WhatsApp Account", self.whatsapp_account)
        self._token = settings.get_password("token")  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._url = settings.url  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._version = settings.version  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._business_id = settings.business_id  # nosemgrep: frappe-modifying-but-not-committing-other-method
        self._app_id = settings.app_id  # nosemgrep: frappe-modifying-but-not-committing-other-method

        self._headers = {  # nosemgrep: frappe-modifying-but-not-committing-other-method
            "authorization": f"Bearer {self._token}",
            "content-type": "application/json",
        }

    def on_trash(self):
        self.get_settings()
        url = f"{self._url}/{self._version}/{self._business_id}/message_templates?name={self.actual_name}"
        try:
            make_request("DELETE", url, headers=self._headers)
        except Exception:
            res = frappe.flags.integration_request.json().get("error", {})
            if res.get("error_user_title") == "Message Template Not Found":
                frappe.msgprint(
                    "Deleted locally", res.get("error_user_title", "Error"), alert=True
                )
            else:
                frappe.throw(
                    msg=res.get("error_user_msg"),
                    title=res.get("error_user_title", "Error"),
                )

    def get_header(self):
        """Get header format."""
        header = {"type": "header", "format": self.header_type}
        if self.header_type == "TEXT":
            header["text"] = self.header
            if self.sample:
                samples = self.sample.split(", ")
                header.update({"example": {"header_text": samples}})
        else:
            pdf_link = ''
            if not self.sample:
                key = frappe.get_doc(self.doctype, self.name).get_document_share_key()
                link = get_pdf_link(self.doctype, self.name)
                pdf_link = f"{frappe.utils.get_url()}{link}&key={key}"
            header.update({"example": {"header_handle": [self._media_id]}})

        return header

@frappe.whitelist()
def fetch():
    """Fetch templates from meta."""
    """Later improve this code to pass a whatsapp account remove the js funcation so that it is called from whatsapp account doctype """
    whatsapp_accounts = frappe.get_all('WhatsApp Account', filters={'status': 'Active'}, fields=['name', 'token', 'url', 'version', 'business_id'])
    invalid_templates = []

    for account in whatsapp_accounts:
        # get credentials
        token = frappe.get_doc("WhatsApp Account", account.name).get_password("token")
        url = account.url
        version = account.version
        business_id = account.business_id

        headers = {"authorization": f"Bearer {token}", "content-type": "application/json"}

        try:
            # Paginate through all pages of templates from Meta.
            next_url = f"{url}/{version}/{business_id}/message_templates"
            seen_urls = set()
            all_templates = []

            while next_url and next_url not in seen_urls:
                seen_urls.add(next_url)
                response = make_request("GET", next_url, headers=headers)
                all_templates.extend(response.get("data", []))
                paging = response.get("paging") or {}
                next_url = paging.get("next")

            for template in all_templates:
                try:
                    parameter_format, body_text, sample_values, named_examples = parse_remote_body(template)
                except Exception as exc:
                    message = f"{template.get('name', '<unnamed>')}: {exc}"
                    invalid_templates.append(message)
                    frappe.log_error(message, "WhatsApp Template Import Validation")
                    continue

                # set flag to insert or update
                flags = 1
                if frappe.db.exists("WhatsApp Templates", {"actual_name": template["name"]}):
                    doc = frappe.get_doc("WhatsApp Templates", {"actual_name": template["name"]})
                else:
                    flags = 0
                    doc = frappe.new_doc("WhatsApp Templates")
                    doc.template_name = template["name"]
                    doc.actual_name = template["name"]

                doc.status = template["status"]
                doc.language_code = template["language"]
                doc.category = template["category"]
                doc.id = template["id"]
                doc.whatsapp_account = account.name
                if template.get("parameter_format"):
                    doc.parameter_format = parameter_format
                elif doc.parameter_format == "NAMED":
                    doc.parameter_format = "POSITIONAL"
                doc.template = body_text
                if parameter_format == "POSITIONAL":
                    doc.sample_values = sample_values
                else:
                    doc.named_example_values = named_examples

                if flags and parameter_format == "NAMED" and doc.named_field_mapping:
                    try:
                        local_mappings = _json_object(doc.named_field_mapping, "Named field mapping")
                        current_names = body_parameter_identities(body_text, parameter_format)
                        stale = sorted(set(local_mappings) - set(current_names))
                        if stale:
                            message = (
                                f"{template['name']}: retained stale local named mapping(s): "
                                + ", ".join(stale)
                            )
                            invalid_templates.append(message)
                            frappe.log_error(message, "WhatsApp Template Import Validation")
                    except Exception as exc:
                        message = f"{template['name']}: retained invalid local named mapping: {exc}"
                        invalid_templates.append(message)
                        frappe.log_error(message, "WhatsApp Template Import Validation")

                # update components
                for component in template["components"]:

                    # update header
                    if component["type"] == "HEADER":
                        doc.header_type = component["format"]

                        # if format is text update sample text
                        if component["format"] == "TEXT":
                            doc.header = component["text"]
                    # Update footer text
                    elif component["type"] == "FOOTER":
                        doc.footer = component["text"]

                    # update template text
                    elif component["type"] == "BODY":
                        # The body and its examples were validated before mutating this document.
                        continue

                    # Update buttons
                    elif component["type"] == "BUTTONS":
                        doc.set("buttons", [])
                        frappe.db.delete("WhatsApp Button", {"parent": doc.name, "parenttype": "WhatsApp Templates"})
                        typeMap = {
                            "URL": "Visit Website",
                            "PHONE_NUMBER": "Call Phone",
                            "QUICK_REPLY": "Quick Reply",
                            "FLOW": "Flow",
                            "MPM": "Multi-Product Message",
                            "CATALOG": "Catalog"
                        }

                        for i, button in enumerate(component.get("buttons", []), start=1):
                            btn_type_raw = button.get("type")
                            if btn_type_raw not in typeMap:
                                frappe.log_error("WhatsApp Fetch Error", f"Unknown WhatsApp Button Type: {btn_type_raw}")
                                continue

                            btn = {}
                            btn["button_type"] = typeMap[button["type"]]
                            btn["button_label"] = button.get("text")
                            btn["sequence"] = i

                            if button["type"] == "URL":
                                btn["website_url"] = button.get("url")
                                if "{{" in btn["website_url"]:
                                    btn["url_type"] = "Dynamic"
                                else:
                                    btn["url_type"] = "Static"

                                if button.get("example"):
                                    btn["example_url"] = ",".join(button["example"])
                            elif button["type"] == "PHONE_NUMBER":
                                btn["phone_number"] = button.get("phone_number")
                            elif button["type"] == "FLOW":
                                btn["flow"] = button.get("flow")

                            doc.append("buttons", btn)

                upsert_doc_without_hooks(doc, "WhatsApp Button", "buttons")

            if invalid_templates:
                return "Fetched templates with invalid state: " + " | ".join(invalid_templates)
            return "Successfully fetched templates from meta"

        except Exception as e:
            # Check if frappe.flags.integration_request is set and has a .json() method
            if hasattr(frappe.flags.integration_request, 'json'):
                try:
                    res = frappe.flags.integration_request.json().get("error", {})
                    error_message = res.get("error_user_msg", res.get("message"))
                    frappe.throw(
                        msg=error_message,
                        title=res.get("error_user_title", "Error"),
                    )
                except (json.JSONDecodeError, KeyError):
                    # Handle cases where the response is not valid JSON or lacks the 'error' key
                    frappe.throw(f"An unexpected error occurred while fetching templates: {e}")
            else:
                # Handle cases where frappe.flags.integration_request doesn't exist or isn't a proper response object
                frappe.throw(f"An unexpected server error occurred: {e}")

def upsert_doc_without_hooks(doc, child_dt, child_field):
    """Insert or update a parent document and its children without hooks."""
    if frappe.db.exists(doc.doctype, doc.name):
        doc.db_update()
        frappe.db.delete(child_dt, {"parent": doc.name, "parenttype": doc.doctype})
    else:
        doc.db_insert()
    for d in doc.get(child_field):
        d.parent = doc.name
        d.parenttype = doc.doctype
        d.parentfield = child_field
        d.db_insert()
