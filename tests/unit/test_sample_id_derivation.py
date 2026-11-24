"""net build sample-id derivation from profiler file paths."""

from __future__ import annotations

from pathlib import Path

from gmeta.cli import _sample_id_from_profile


def test_specific_filename_wins() -> None:
    assert _sample_id_from_profile("kraken/FZZJ26HZSC0015.report") == "FZZJ26HZSC0015"
    assert _sample_id_from_profile("x/1.kreport") == "1"
    assert _sample_id_from_profile("x/SAMPLE.fastq.report") == "SAMPLE.fastq"


def test_generic_artifact_uses_gmeta_run_layout(tmp_path: Path) -> None:
    # gmeta run layout: <outdir>/<sample>/pipeline/kreport.txt
    path = tmp_path / "out" / "S1" / "pipeline" / "kreport.txt"
    assert _sample_id_from_profile(path) == "S1"
    assert _sample_id_from_profile(tmp_path / "out" / "S1" / "pipeline" / "bracken.txt") == "S1"
    assert _sample_id_from_profile(tmp_path / "out" / "S1" / "pipeline" / "profile.tsv") == "S1"


def test_plain_generic_name_keeps_stem(tmp_path: Path) -> None:
    # outside a run layout there is no reliable sample id in the path
    assert _sample_id_from_profile(tmp_path / "kreports" / "SAMPLE-A" / "kreport.txt") == "kreport"
