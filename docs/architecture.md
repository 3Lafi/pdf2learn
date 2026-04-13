# pdf2learn architecture

One-page module map. Enforced by `tests/unit/test_layering.py`.

## Data flow

```
CLI (cli.py)
    │
    ▼
Orchestrator (orchestrator.py)
    │   run_job / run_batch / iter_pdfs
    │
    ├─► Extract (extract/)        PDF bytes ──► ExtractedContent
    │       marker_engine.py      runs marker-pdf, persists figure images
    │       html_parser.py        parses marker HTML ──► Section/Block tree
    │
    └─► Render (render/)          ExtractedContent ──► RenderedDocument
            renderer.py           Jinja2 env, asset copy, TOC build
            templates/            base.html.j2 + partials/
            (assets/ shipped alongside)
```

## Layering rules

| Layer         | May import                              | Must NOT import                     |
|---------------|-----------------------------------------|-------------------------------------|
| `models`      | stdlib only                             | anything in `pdf2learn`             |
| `config`      | `models`                                | `extract`, `render`, `orchestrator` |
| `paths`       | stdlib                                  | `extract`, `render`, `orchestrator` |
| `logging_`    | stdlib                                  | `extract`, `render`, `orchestrator` |
| `extract/`    | `models`, `config`                      | `render`, `orchestrator`, `cli`     |
| `render/`     | `models`, `config`, `paths`             | `extract`, `orchestrator`, `cli`    |
| `orchestrator`| all of the above                        | `cli`                               |
| `cli`         | `orchestrator`, `config`, `__init__`    | —                                   |

`extract/` and `render/` are siblings that never speak to each other; the
orchestrator is the only place the two halves meet.

## Where do I change X?

| Task                                             | File                                            |
|--------------------------------------------------|-------------------------------------------------|
| Add a new CLI flag                               | `cli.py` + `config.py`                          |
| Change how a PDF is turned into blocks           | `extract/html_parser.py`                        |
| Swap the extraction engine                       | `extract/marker_engine.py`                      |
| Change HTML structure / landmarks                | `render/templates/base.html.j2`                 |
| Add a block type (e.g. callout)                  | `models.py` + `html_parser.py` + `partials/`    |
| Restyle output                                   | `src/pdf2learn/assets/style.css`                |
| Change theme toggle behavior                     | `src/pdf2learn/assets/toggle.js`                |
| Change output directory naming / re-run policy   | `paths.py`                                      |
| Change log format / prefixes                     | `logging_.py`                                   |
| Change exit-code mapping                         | `orchestrator.py`                               |

## Invariants

* `ExtractedContent` is the only type crossing the extract↔render boundary.
* Rendering is pure: given the same `ExtractedContent` + asset dir, output is
  byte-stable modulo timestamps (which live in `conversion.log`, not HTML).
* Failures in `extract/` raise `ImageOnlyPDFError` (exit 3) or
  `ExtractionError` (exit 4); `orchestrator.run_job` is the single place
  those exceptions are mapped to exit codes.
