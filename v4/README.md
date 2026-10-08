# v4 private distribution

Build the extension from huming0018-dot/crawler-extension/v4 first, then run:

```sh
python3 v4/test_release.py /path/to/crawler-extension/v4
python3 v4/build_trial.py --source /private/crowd-extension-v4.0.6.zip \
  --invitation-file /private/mac-trial.json --output /private/Mac轻量内测-v4.0.6.zip
```

The invitation file is the existing bounded, unexpired Mac trial. This command
never enrolls, changes the invitation, uploads a file, signs CRX, alters
updates.xml or opens a distribution channel. Do not commit the output ZIP or
invitation file. The helper updates an existing v4 profile only; do not uninstall
or load into the legacy v3 profile (the historical public key/ID is shared).

4.0.6 validates the source protocol/version/worker and every delivered file before
adding the private invitation. It updates config hashes afterward and generates
matching version text in the guide. In the original browser the participant must
refresh the extension and verify 4.0.6; the helper cannot silently authorize it.

Current package: 44,846 bytes; SHA256
`afa5298cafc1d393166149857eb4b277ddf08f4fd11387252e0d6366ae7d6708`.
No real Mac acceptance yet. Existing root Pages and 3.4.14 update artifacts are
untouched. Full handoff: crowd-kol/docs/V4_ITERATION.md on codex/v4.0.6-handoff.
