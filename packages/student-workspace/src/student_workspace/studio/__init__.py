"""Application Studio: resumes stored as data, typeset with Typst, edited directly.

- `db.py`: the SQLite database in the workspace and its migrations.
- `store.py`: every read and change; the CLI and the app both go through it.
- `markup.py`: the small inline markup in resume text (**bold**, *italic*, [text](url)).
- `render.py`: Typst templates, compiling, bullet positions, standalone export source.
- `export.py`: writes resume-YYYY-MM-DD.typ/.pdf into the application folder.
- `importer.py`: reads an existing Jake's-style LaTeX resume and evidence matrix.
- `ats.py`: parse check of the PDF and keyword coverage against a posting.
- `handoff.py`: "Ask the AI" through application handoffs, and importing its variants.
"""
