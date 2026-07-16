# Hiring Radar Dashboard Source

This directory contains the editable source code for the Hiring Radar static HTML dashboard.

The dashboard compiler (`app/dashboard/build.py`) resolves `## include <relative/path>` statements recursively to compile the source into a single self-contained HTML file.

## Include Syntax

To include another file inside any template, script, or stylesheet, use this syntax on its own line:
```html
## include <path/relative/to/src/root>
```

Example inside `dashboard.htmlx`:
```html
## include components/header.html
```

## Directory Structure

- `dashboard.htmlx`: The main entrypoint template.
- `components/`: HTML component partials (header, tables, modals).
- `styles/`: Modular stylesheets cascading variables (tokens, base, component styles).
- `scripts/`: Modular JavaScript scripts (state, filters, charts, modals, and the DOMContentLoaded initialization handler in `main.js`).
