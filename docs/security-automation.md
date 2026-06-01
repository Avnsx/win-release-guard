# Security Automation

Detailed automation documentation now lives in the GitHub Wiki:

https://github.com/Avnsx/win11_release_guard/wiki/Automation-and-Security

Repository invariants kept here for local agents and tests:

- Dependabot is configured in `.github/dependabot.yml`.
- CodeQL code scanning is configured by `.github/workflows/codeql.yml`.
- If GitHub code scanning is disabled, enable it under
  `Settings -> Code security and analysis -> Code scanning`.
- GitHub UI settings are not fully controlled by repository files.
- README badges are workflow status badges, not external guarantees.

## GitHub Actions Pinning

- GitHub-owned first-party actions may use audited major tags.
- Audited major tags are enforced by `tools/check_github_action_versions.py`.
- Third-party actions are forbidden unless explicitly allowlisted and pinned to
  a full 40-character commit SHA.
- Adding any third-party action requires updating the audit tool, tests, and
  this document with the reason for the exception.
- Workflow permissions stay minimal; production publishing must not request
  `contents: write`.
