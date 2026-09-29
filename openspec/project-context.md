# Project Context: frappe_whatsapp

## Stack
- Python package `frappe_whatsapp`, Python `>=3.10`, distributed through Frappe Bench/Flit.
- Frappe Framework application using DocTypes, hooks, patches, server-side Python, and JavaScript assets.

## Testing and quality
- CI provisions Frappe Bench with MariaDB and Redis and runs `bench --site test_site run-tests --app frappe_whatsapp` from the bench root. This is not a standalone command available from this app checkout without a configured bench and site.
- Tests are located under `frappe_whatsapp/frappe_whatsapp/tests`.
- CI's Pylint workflow runs `pylint $(git ls-files '*.py')`; no type checker, formatter, coverage command, or E2E runner was identified.
- Strict TDD is disabled: the repository has no explicit workspace-wide test command, and the CI test command depends on an initialized bench and services.

## Scope
This initialization describes only the standalone `apps/frappe_whatsapp` repository. Parent-repository project discovery was intentionally excluded.
