# Databases

gmeta resolves every database under one root. The default is always outside
the code: the XDG data home (`~/.local/share/gmeta/db`) — databases are
tens-of-GB external downloads and never live in the package or the repo.
For servers, set `GMETA_DB_DIR` (or `-D`) to a data volume:

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

### Coverage references in one step

For 种基因组覆盖度 you need per-species reference FASTAs. Instead of
fetching by hand, feed the missing list from `net build` back into
`db fetch refs`:

```bash
gmeta net build kraken/*.report --reads-dir raw_reads --ref-dir refs \
  -o 识别网上报.xlsx --missing-refs-out missing_refs.tsv
gmeta db fetch refs --missing-refs missing_refs.tsv -O scripts/
bash scripts/fetch-refs.sh        # NCBI datasets: one genome per taxid
```

The script installs `refs/<taxid>_<accession>.fna` (matched by `--ref-dir`
without a manifest) and appends to `refs/manifest.csv`. It uses the
**NCBI Datasets CLI** (`datasets` binary; the Python `pylib` is deprecated
upstream):

```bash
conda install -c conda-forge ncbi-datasets-cli
```

The script tolerates CLI dialect differences (JSON-lines vs pretty JSON,
`--reference` support, and the legacy `taxon` subcommand for old binaries)
and, when a taxid fails, prints the CLI's own error instead of a bare
warning. If the error is `unknown command "taxid"`, the installed binary is
the retired v1-era CLI — upgrade it (`conda install -c conda-forge
ncbi-datasets-cli`) or install the standalone v2 binary.
`export NCBI_API_KEY=…` raises the API rate limit for large batches. You can
also pass explicit taxids: `--taxids 562,662`.

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
