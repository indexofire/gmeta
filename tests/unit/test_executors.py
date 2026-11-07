"""Executor modules for centrifuge/kaiju/metaphlan/kmcp.

External tools are faked with small shell scripts placed on GMETA_PIXI_BIN —
this exercises the real resolution (config.which → pixi_path) and subprocess
path while keeping the tests hermetic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gmeta.analysis.centrifuge import profile_centrifuge, resolve_centrifuge_db
from gmeta.analysis.kaiju import profile_kaiju
from gmeta.analysis.kmcp import profile_kmcp
from gmeta.analysis.metaphlan import profile_metaphlan

KREPORT_FAKE = (
    "100.00\t1000\t0\tR\t1\troot\n"
    " 40.00\t400\t0\tS\t9606\t  Homo sapiens\n"
    " 25.00\t250\t0\tS\t662\t  Vibrio cholerae\n"
    " 40.00\t400\t400\tU\t0\tunclassified\n"
)

ARG_PARSER = r"""
out=""; rank=""; prev=""
for a in "$@"; do
  case "$prev" in
    -o|--out-file) out="$a" ;;
    -r) rank="$a" ;;
  esac
  prev="$a"
done
"""


def _write_bin(fakedir: Path, name: str, body: str) -> None:
    script = fakedir / name
    script.write_text("#!/usr/bin/env bash\n" + body)
    script.chmod(0o755)


@pytest.fixture
def fake_bin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fakedir = tmp_path / "fakebin"
    fakedir.mkdir()
    monkeypatch.setenv("GMETA_PIXI_BIN", str(fakedir))
    return fakedir


@pytest.fixture
def reads(tmp_path: Path) -> list[Path]:
    paths = []
    for name in ("sample_R1.fq", "sample_R2.fq"):
        path = tmp_path / name
        path.write_text("@r1\nACGT\n+\nIIII\n")
        paths.append(path)
    return paths


# --- centrifuge -----------------------------------------------------------


def test_centrifuge_profile(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    db = tmp_path / "cfdb"
    db.mkdir()
    (db / "p_compressed.1.cf.index").touch()

    _write_bin(fake_bin, "centrifuge", 'echo "R1\\t562\\t1\\t60\\t+"\n')
    _write_bin(
        fake_bin,
        "centrifuge-kreport",
        f"printf '{KREPORT_FAKE}'\n",
    )

    work = tmp_path / "work"
    result = profile_centrifuge(reads, db, threads=1, work_dir=work)

    assert result.method == "centrifuge"
    assert result.result["total_reads"] == 1400
    assert result.result["classified_reads"] == 1000
    assert result.result["n_species"] == 2
    assert (work / "centrifuge.tsv").is_file()
    kreport = (work / "kreport.txt").read_text()
    assert "Vibrio cholerae" in kreport


def test_resolve_centrifuge_db_missing(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="centrifuge index not found"):
        resolve_centrifuge_db(tmp_path / "nowhere")


# --- kaiju ----------------------------------------------------------------


def test_kaiju_profile(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    db = tmp_path / "kaijudb"
    db.mkdir()
    (db / "nodes.dmp").touch()
    (db / "names.dmp").touch()
    (db / "kaiju_db.fmi").touch()

    _write_bin(fake_bin, "kaiju", ARG_PARSER + 'printf "C\\tread1\\t562\\n" > "$out"\n')
    _write_bin(
        fake_bin,
        "kaiju2table",
        ARG_PARSER
        + """\
{
  printf 'file\\tpercent\\treads\\ttaxon_id\\ttaxon_name\\n'
  if [ "$rank" = species ]; then
    printf 'x.fq\\t60.0\\t600\\t562\\tBacteria; Escherichia; Escherichia coli\\n'
    printf 'x.fq\\t25.0\\t250\\t662\\tBacteria; Vibrio; Vibrio cholerae\\n'
  else
    printf 'x.fq\\t60.5\\t605\\t561\\tBacteria; Escherichia\\n'
    printf 'x.fq\\t25.0\\t250\\t641\\tBacteria; Vibrio\\n'
  fi
} > "$out"
""",
    )

    work = tmp_path / "work"
    result = profile_kaiju(reads, db, threads=1, work_dir=work)

    assert result.method == "kaiju"
    assert result.result["n_species"] == 2
    top = result.result["top_species"][0]
    assert top["name"] == "Escherichia coli"
    assert top["reads"] == 600
    assert (work / "kaiju.species.tsv").is_file()
    assert (work / "kaiju.genus.tsv").is_file()
    assert (work / "kaiju.out").is_file()


def test_kaiju_missing_db(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    with pytest.raises(RuntimeError, match="kaiju database not found"):
        profile_kaiju(reads, tmp_path / "empty", threads=1)


# --- metaphlan ------------------------------------------------------------


def test_metaphlan_profile(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    db = tmp_path / "mpadb"
    db.mkdir()
    (db / "mpa_vOct24_CHOCOPhlanSGB_202403").touch()

    _write_bin(
        fake_bin,
        "metaphlan",
        ARG_PARSER
        + """\
{
  printf '#clade_name\\tNCBI_tax_id\\trelative_abundance\\tadditional_species\\n'
  printf 'g__Escherichia\\t561\\t55.5\\t\\n'
  printf 's__Escherichia_coli\\t562\\t50.5\\t\\n'
  printf 's__Vibrio_cholerae\\t662\\t4.2\\t\\n'
} > "$out"
""",
    )

    work = tmp_path / "work"
    result = profile_metaphlan(reads, db, threads=1, work_dir=work)

    assert result.method == "metaphlan"
    assert result.result["n_species"] == 2
    assert result.result["top_species"][0]["name"] == "Escherichia coli"
    assert (work / "profile.tsv").is_file()


# --- kmcp -----------------------------------------------------------------


def test_kmcp_profile(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    db = tmp_path / "kmcpdb"
    (db / "R001").mkdir(parents=True)
    (db / "R001" / "_block001.uniki").touch()
    (db / "taxid.map").write_text("GCF_1\t562\n")
    taxdump = db / "taxdump"
    taxdump.mkdir()
    (taxdump / "nodes.dmp").touch()
    (taxdump / "names.dmp").touch()

    _write_bin(
        fake_bin,
        "kmcp",
        """\
sub=$1; shift
"""
        + ARG_PARSER
        + """\
if [ "$sub" = search ]; then
  echo "#query" | gzip > "$out"
else
  {
    printf '#ref\\tpercentage\\tcoverage\\tscore\\tchunksFrac\\tchunksRelDepth\\tchunksRelDepthStd\\treads\\tureads\\thicureads\\trefsize\\trefname\\ttaxid\\trank\\ttaxname\\ttaxpath\\ttaxpathsn\\n'
    printf 'GCF_1\\t55.0\\t0.9\\t0.9\\t0.9\\t1\\t0\\t600\\t550\\t550\\t4600000\\tEcoli\\t562\\tspecies\\tEscherichia coli\\t562\\t561|562\\n'
    printf 'GCF_2\\t5.0\\t0.9\\t0.9\\t0.9\\t1\\t0\\t50\\t45\\t45\\t4500000\\tVchol\\t662\\tspecies\\tVibrio cholerae\\t662\\t641|662\\n'
  } > "$out"
fi
""",
    )

    work = tmp_path / "work"
    result = profile_kmcp(reads, db, threads=1, work_dir=work)

    assert result.method == "kmcp"
    assert result.result["n_species"] == 2
    assert result.result["top_species"][0]["name"] == "Escherichia coli"
    assert (work / "search.tsv.gz").is_file()
    assert (work / "profile.tsv").is_file()


def test_kmcp_missing_db(tmp_path: Path, fake_bin: Path, reads: list[Path]) -> None:
    with pytest.raises(RuntimeError, match="kmcp database not found"):
        profile_kmcp(reads, tmp_path / "empty", threads=1)


# --- gmeta run end-to-end (fake fastp + centrifuge) ------------------------


def test_cli_run_centrifuge(
    tmp_path: Path, fake_bin: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from click.testing import CliRunner

    from gmeta.cli import main

    db = tmp_path / "cfdb"
    db.mkdir()
    (db / "p.1.cf.index").touch()

    r1 = tmp_path / "r1.fq"
    r2 = tmp_path / "r2.fq"
    r1.write_text("@r1\nACGT\n+\nIIII\n")
    r2.write_text("@r2\nACGT\n+\nIIII\n")

    _write_bin(
        fake_bin,
        "fastp",
        r"""out1=""; out2=""; json=""; prev=""
for a in "$@"; do
  case "$prev" in
    --out1) out1="$a" ;;
    --out2) out2="$a" ;;
    --json) json="$a" ;;
  esac
  prev="$a"
done
: > "$out1"
[ -n "$out2" ] && : > "$out2"
cat > "$json" <<'EOF'
{"summary":{"before_filtering":{"total_reads":100,"total_bases":15000,"q20_rate":0.97,"q30_rate":0.93},"after_filtering":{"total_reads":90,"total_bases":13000,"q20_rate":0.98,"q30_rate":0.95,"read1_mean_length":150,"read2_mean_length":150}},"filtering_result":{},"duplication":{"rate":0.1},"read1_before_filtering":{"total_reads":100},"read2_before_filtering":{"total_reads":100}}
EOF
""",
    )
    _write_bin(fake_bin, "centrifuge", 'echo "R1\\t562\\t1\\t60\\t+"\n')
    _write_bin(fake_bin, "centrifuge-kreport", f"printf '{KREPORT_FAKE}'\n")

    outdir = tmp_path / "out"
    result = CliRunner().invoke(
        main,
        [
            "run",
            str(r1),
            str(r2),
            "-s",
            "SAMPLE-1",
            "-m",
            "centrifuge",
            "-D",
            str(db),
            "-O",
            str(outdir),
            "-f",
            "json",
        ],
    )
    assert result.exit_code == 0, result.output

    # stderr (progress lines) is mixed into CliRunner output; JSON starts at "{"
    payload = json.loads(result.output[result.output.index("{") :])
    assert payload["method"] == "centrifuge"
    assert payload["qc"]["total_reads"] == 200  # fastp pairs × 2
    assert payload["n_species"] == 2
    assert (outdir / "SAMPLE-1.report.json").is_file()
