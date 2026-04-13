# Output

This directory is populated by `pdf2learn` at runtime. It ships empty on purpose — per-PDF conversion artifacts live here, organized as:

```
output/
└── <pdf-slug>/
    ├── index.html
    ├── conversion.log
    └── assets/
        ├── style.css
        ├── toggle.js
        └── <pdf-slug>_fig001.png
```

Re-runs against the same PDF default to a timestamped subdirectory (`output/<slug>/20260413-142530/`) so prior runs are preserved. Pass `--force` to overwrite in place.

The directory itself (minus this README) is gitignored.
