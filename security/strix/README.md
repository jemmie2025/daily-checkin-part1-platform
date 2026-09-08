# Strix Authorised Security Gate

Strix is an active security test and is deliberately separated from ordinary
pull-request validation. Run it only through the manual `Security gates`
workflow after the repository or staging target has been authorised.

The repository scan runs non-interactively in quick, diff-scoped mode:

```bash
strix -n --target ./ --scan-mode quick --scope-mode diff --diff-base origin/main
```

Requirements:

- a trusted runner with Docker available;
- `STRIX_LLM` and `LLM_API_KEY` supplied through approved GitHub environment
  secrets;
- full Git history for diff scoping;
- a named security reviewer; and
- no production tokens or unapproved network targets.

Exit code 2 means vulnerabilities were found and blocks promotion. Exit code 1
means the scan failed and also blocks promotion. Reports must be reviewed and
sanitized before being attached to Redmine.
