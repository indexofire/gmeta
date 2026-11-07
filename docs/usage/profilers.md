# Supported profilers

Six profilers, each importable **and** executable. Import paths accept the
formats below; execution (`gmeta run -m …`) shells out to the tool from the
pixi environment.

## kraken2 + bracken

- **Import**: kreport (tree format) and/or bracken species table.
- **Execute**: `gmeta run -m kraken2` runs kraken2 then bracken; read length
  for bracken comes from the database's `databaseXXXmers.kmer_distrib` file.
- kreport column order matters: `percent | clade reads | direct reads |
  rank | taxid | indented name`. gmeta pairs species to their genus via the
  name indentation — real genus clade counts.

## centrifuge

- **Import**: native report (`name taxID taxRank genomeSize numReads
  numUniqueReads abundance`) or any kraken-style kreport (e.g. from
  `centrifuge-kreport`).
- **Execute**: `gmeta run -m centrifuge` classifies, converts with
  `centrifuge-kreport`, and reuses the kraken2 kreport path — the 识别网
  export gets the same tree-exact genus pairing.

## kaiju

- **Import**: `kaiju2table` output (`file percent reads taxon_id taxon_name`).
  Pass the species table as the profile; `--kaiju-genus` adds real genus
  counts. Lineage names ("Bacteria; Escherichia; Escherichia coli") are
  parsed for genus hints.
- **Execute**: `gmeta run -m kaiju` runs kaiju then kaiju2table for both
  species and genus ranks.

## metaphlan

- **Import**: profile with `#clade_name NCBI_tax_id relative_abundance …`
  rows; `rel_ab_w_read_stats` additionally fills 种序列数 (estimated reads).
- **Execute**: `gmeta run -m metaphlan` runs `metaphlan -t rel_ab_w_read_stats`
  with `--bowtie2db $DB_DIR/metaphlan`.

## kmcp

- **Import**: `kmcp profile` 17-column TSV; requires the `taxid`/`rank`/
  `taxname` columns (present when the database was built with a taxid map).
  Per-reference rows are aggregated by taxid.
- **Execute**: `gmeta run -m kmcp` runs `kmcp search` (single-end mode for
  sensitivity, per the official recommendation) then `kmcp profile
  --level species`. Needs the NCBI taxdump under `$DB_DIR/taxdump`.
- Note: KMCP percentages are per-reference; cross-check totals against the
  审核明细 sheet.

## sylph

- **Import**: profile TSV (`Genome_file`, `Adjusted_ANI`, `Taxonomic_abundance`).
- **Execute**: `gmeta run -m sylph` runs sketch + profile; confidence bands
  follow ANI (high ≥95%, medium ≥90%).

## Format sniffing

`net build` auto-detects each input file; `--profiler` forces one. The
sniffer distinguishes headers (kaiju, metaphlan, kmcp, bracken, sylph) from
headerless layouts (centrifuge's name-led columns, kraken2's percent-led
kreport).
