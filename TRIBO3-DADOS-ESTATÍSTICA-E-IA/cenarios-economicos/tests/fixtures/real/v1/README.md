# Real public-data fixtures v1

This directory contains small, immutable extracts collected from external data
providers. They exist only for deterministic offline tests and are not refreshed
automatically.

The Bacen file contains the twelve monthly IPCA observations published by SGS
for 2024. The repository adds one terminal line feed to the collected JSON; the
manifest preserves both the upstream hash and the checked-in hash.

The Ibovespa file contains the first five ordered observations of the 2024
provider extract. Yahoo Finance and yfinance are not official B3 sources. The
sample must not be described as official B3 data or used as evidence of an
approved actuarial assumption.

Every file is covered by `fixture-manifest.json`, including byte count, SHA-256,
collection timestamp, requested period, collector version and provenance. A
content change requires a new fixture-set version instead of overwriting `v1`.

No ANBIMA fixture was added. The live response observed during this phase did
not satisfy the experimental spike contract, so freezing it would incorrectly
promote an invalid response. ANBIMA remains covered only by the explicit opt-in
live test and its synthetic parser fixtures.
