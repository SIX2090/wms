# Bundled JavaScript parser

`esprima/` contains the unmodified Python source files from `esprima-fork` 5.0.0.
It is bundled for `scripts/fetch_ast.py` so the pre-commit hook continues to work
offline with `python -I -S`, without installing packages into the WMS runtime.

- Upstream distribution: https://pypi.org/project/esprima-fork/5.0.0/
- Wheel: `esprima_fork-5.0.0-py3-none-any.whl`
- Wheel SHA-256: `3c3280a9c1e40e837bf5183625ba0fe2d75b946f66040983da603863e3145b74`
- Licenses and notices: `esprima_fork-5.0.0.dist-info/licenses/`
- Imported files: the 27 `esprima/*.py` sources; no wheel installation, startup
  hook, executable script or network access is needed.

2026-11-09: the scanner limits each script to 1 MiB, 300,000 parser nodes and a
30-second cooperative analysis budget. Unsupported syntax, excessive nesting
or resource exhaustion rejects JS checking. Inline template scripts retain the
existing warning policy; `--templates-strict` makes those findings fail.

Updates must retain upstream copyright and license notices, verify the source
distribution hash, and rerun syntax, alias, staged-index, hook and real-script
regressions. Do not replace the parser silently from an installed site package.
