# Legacy participant 105 compatibility candidate

Base: published 4.2.93 source commit `d0129be`, all 30 provenance source hashes exact. This is a separate legacy build, not a rollback of current 104/native-v2 source. `legacy105.patch` plus `BUILD-METADATA.json` may be stored as compatibility build assets on the current source branch; do not overlay this historical source tree over 104.

Four source changes: manifest/core version105; updater.status adds fixed local-only `update_track=legacy_participant` and `pro_readiness=not_reported`; existing update UI shows the legacy track and that Pro readiness has not been reported. No acquisition implementation, Stop, identity, account, task, outbox, native verb or permission change. No Pro/SDK/runtime/helper is added.

These two fields are not new cloud fields. Existing node version/release registration and OTA started/waiting/completed/skipped telemetry remain unchanged. An actual 105 completed event would prove extension OTA only, not Pro availability or source acceptance.

Build: archive `v4` at exact base commit from BASELINE.json into an empty scratch directory, apply `legacy105.patch` at that directory, then run `python3 v4/build.py --profile participant --output <output>/crowd-v4.2.105-legacy-extension.zip`. New test: `node v4/tests/legacy-ota-bridge.cjs`. Existing telemetry/quiescence/parking tests pass. Existing updater-preferences test fails its unrelated local-test 1-minute expectation on both unchanged93 and candidate105 (actual60); both RED logs retained, no assertion changed.

The old helper accepts extension-only swaps under its original signature/key/manifest/identity checks. It has no reviewed remote dependency installation or private SDK delivery action. The remote SDK/descriptor state remains unknown; no-user Pro migration cannot be claimed from this OTA. A lawful private SDK and reviewed full bootstrap remain required for actual Pro use; this candidate only restores progress of the old extension channel.

No signature/channel has been created or changed. Proposed target after independent review is only `channel-participants.json`; preserve other channels, especially old Pro99 and native-v2 104. Root alone signs/publishes; next natural alarm must independently confirm real application.
