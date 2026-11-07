# Databases

gmeta resolves every database under one root. The default is location-aware:
a repo checkout uses `<repo>/data/db` (gitignored), an installed package
uses the XDG data home (`~/.local/share/gmeta/db`) — databases are
tens-of-GB external downloads and never live inside the package. Override
with `GMETA_DB_DIR` or `-D`:

| Tool | Expected under `$DB_DIR/` | Required files |
| --- | --- | --- |
| kraken2 + bracken | `kraken2/` | `*.k2d` + `databaseXXXmers.kmer_distrib` |
| centrifuge | `centrifuge/` | `<prefix>.1.cf.index*` |
| kaiju | `kaiju/` | `nodes.dmp`, `names.dmp`, `*.fmi` |
| metaphlan | `metaphlan/` | `mpa_v*/` or `*.bt2l*` |
| kmcp | `kmcp/` | `*.uniki` + `taxid.map` (+ `taxdump/` with `nodes.dmp`) |
| sylph | `sylph/` | `*.syldb` / `*.syl2db` |
| host removal | `host/` | bowtie2 index prefix (e.g. `grch38.1.bt2l`) |

Check what resolves: `gmeta db list` — a Rich table over all eight targets
(ready/missing + the exact missing file); `gmeta db list -f json` is the
stable machine contract. Every probe calls the same resolver the executor
uses, so "ready" means the profiler would accept the path — including
companion files like bracken's `kmer_distrib` or kaiju's `names.dmp`.

## Fetch scripts

Databases are tens of gigabytes — `gmeta db fetch` never downloads. It
writes commented, resumable bash scripts for you to review and run:

```bash
gmeta db fetch                    # scripts for every target → ./db-fetch/
gmeta db fetch kraken2 kmcp -O scripts/ --db-root /data/db

bash scripts/fetch-kraken2.sh     # wget -c → tar → verify layout
bash scripts/run_all.sh           # or run everything in order
```

Each script installs into `$GMETA_DB_DIR` (or the `--db-root` given at
generation time) and verifies the layout gmeta's resolvers expect.

**kmcp is special**: its prebuilt databases ship on OneDrive/CowTransfer
(no stable wget URL). `fetch-kmcp.sh` downloads the NCBI taxdump
automatically, then exits with instructions for the manual database copy —
re-run it after the manual step to finish verification.

URLs move with releases; every URL sits in a variable at the top of its
script with upstream links in comments.

## Reference genomes for 种基因组覆盖度

Coverage needs per-species reference FASTAs plus a manifest CSV:

```csv
accession,species_taxid,organism_taxid,scientific_name,file_path
GCF_000025985.1,817,272559,Bacteroides fragilis NCTC 9343,refs/GCF_000025985.1.fna
```

Relative `file_path` resolves against the manifest's directory. Without a
manifest, `--ref-dir` is searched for `{accession}*.fna` / `{taxid}*.fna`.

## Chinese name tables

`src/gmeta/data/` ships the surveillance name tables
(`species_chinese_names.tsv`, `genus_chinese_names.tsv`,
`taxid_chinese_mapping.csv`); unmapped taxa fall back to their latin names.
The tables ship inside the package (small, versioned with gmeta). Extend
them by editing `src/gmeta/data/*.tsv|csv` and reinstalling; unmapped taxa
fall back to their latin names.
