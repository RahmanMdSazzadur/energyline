# Process flow and disposition

S1 identify/load → B12 → S2 insert four inert parts → B23 → S3 fit/fasten → B34 → S4 inspect/test → B45 → S5 label/release.

Default interstation buffers each hold two waiting units, excluding units at stations. A completed station retains its unit when downstream space is unavailable (blocking after service). Shared operators are explicitly reserved for attended work. A unit can occupy one S3 resource in the parallel manual case, never both.

Defects created upstream retain origin and are perfectly detected at S4 in the base model. Failed inspection routes to an unlimited offline FIFO queue with one dedicated paid rework operator. One failed rework attempt is scrap; a pass rejoins before S5. Unfinished inspection/rework remains WIP at shift end. Accepted output requires S5 completion in the shift window.

In the `integrated_s3` case, failed S3 controller results become S3-origin defects for S4 detection, while faulted uncertain cell cycles are conservatively scrapped. Cell completion is a station record, not good-line output. Each cell cycle and flow unit share an ID; final accepted output is counted once at S5.
