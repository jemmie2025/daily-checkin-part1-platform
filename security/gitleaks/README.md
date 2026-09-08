# Gitleaks Gate

Gitleaks scans the complete Git history on every pull request and push. The CI
checkout uses full history, and findings are redacted from logs.

Local equivalent:

```bash
gitleaks git --redact --verbose --config .gitleaks.toml
```

The custom repository scanner remains as a second, contract-specific control.
Do not add fingerprint allowlists until the finding has been reviewed and
documented as a false positive.
