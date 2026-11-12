# ADR 0062: Licence: GPL-3.0-or-later

- **Status**: Accepted
- **Date**: 2026-11-12

## Context

The repository is public and the Docker image is to be published. `mutagen` (GPL-2.0-or-later) is imported by every module that reads or writes tags, and `Unidecode` and `text-unidecode` (GPL / Artistic) are used for file names. Tagwright and these libraries run in one process, and the image ships them together, so the combined work is GPL. The other Python libraries are MIT, BSD or MIT-CMU; the frontend bundle holds MIT, ISC, BSD, 0BSD and Apache-2.0 code; `rsgain`, `fpcalc` and `drcalc` run as separate programs ([0036](0036-standalone-pipeline-package.md)), so they are an aggregate, not part of Tagwright. A permissive licence (MIT, Apache-2.0) would conflict with the two GPL libraries; replacing `mutagen` would touch every tag access ([0058](0058-audio-files-through-one-seam.md)).

## Decision

- Tagwright is licensed **GPL-3.0-or-later**. `mutagen` and `Unidecode` are "2.0 or later" and can be used under version 3; the Apache-2.0 frontend packages are compatible with version 3, not with 2-only.
- `LICENSE` holds the licence text; `NOTICE` lists the third-party software and says where the source of the Debian packages in the image comes from (the written offer for the GPL and LGPL parts). `pyproject.toml` and `ui/package.json` name the licence, and the image carries the labels `org.opencontainers.image.licenses` and `.source`.
- A new dependency must be GPL-3 compatible (permissive, LGPL, GPL-2-or-later, GPL-3). GPL-2-only, AGPL, "non-commercial" and similar licences are not accepted without a new ADR. New dependencies are added to `NOTICE`.

## Consequences

- The published image and any copy of the code must be offered under the GPL with its source. `drcalc` stays MIT, as its author is the same person.
- Contributions are accepted under the same licence.
