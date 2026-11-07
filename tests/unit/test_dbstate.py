"""Database inventory probes: ready/missing per tool, mirroring the resolvers."""

from __future__ import annotations

from pathlib import Path

from gmeta.dbstate import probe_databases, probes_to_dict


def _by_tool(probes):
    return {probe.tool: probe for probe in probes}


def test_empty_root_reports_everything_missing(tmp_path: Path) -> None:
    probes = probe_databases(tmp_path)
    assert len(probes) == 8
    for probe in probes:
        assert not probe.ready
        # actionable detail: every miss points at a remedy
        assert "gmeta db fetch" in probe.detail or "missing" in probe.detail.lower()


def test_kraken2_ready_needs_kmer_distrib(tmp_path: Path) -> None:
    db = tmp_path / "kraken2"
    db.mkdir()
    (db / "hash.k2d").touch()
    (db / "taxo.k2d").touch()
    (db / "opts.k2d").touch()
    probes = _by_tool(probe_databases(tmp_path))
    assert not probes["kraken2"].ready  # bracken distribution missing
    assert "kmer_distrib" in probes["kraken2"].detail

    (db / "database150mers.kmer_distrib").touch()
    assert _by_tool(probe_databases(tmp_path))["kraken2"].ready


def test_kaiju_partial_state_is_actionable(tmp_path: Path) -> None:
    db = tmp_path / "kaiju"
    db.mkdir()
    (db / "nodes.dmp").touch()
    (db / "kaiju_db.fmi").touch()
    probes = _by_tool(probe_databases(tmp_path))
    assert not probes["kaiju"].ready
    assert "names.dmp" in probes["kaiju"].detail

    (db / "names.dmp").touch()
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "kaiju")


def test_centrifuge_ready_via_index_file(tmp_path: Path) -> None:
    db = tmp_path / "centrifuge"
    db.mkdir()
    (db / "p_compressed.1.cf.index").touch()
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "centrifuge")


def test_metaphlan_ready_via_mpa_dir(tmp_path: Path) -> None:
    db = tmp_path / "metaphlan"
    db.mkdir()
    (db / "mpa_vOct24_CHOCOPhlAnSGB_202403").touch()
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "metaphlan")


def test_kmcp_needs_taxdump(tmp_path: Path) -> None:
    db = tmp_path / "kmcp"
    (db / "R001").mkdir(parents=True)
    (db / "R001" / "_block001.uniki").touch()
    (db / "taxid.map").write_text("GCF_1\t562\n")
    probes = _by_tool(probe_databases(tmp_path))
    assert not probes["kmcp"].ready
    assert "taxdump" in probes["kmcp"].detail

    taxdump = tmp_path / "taxdump"
    taxdump.mkdir()
    (taxdump / "nodes.dmp").touch()
    (taxdump / "names.dmp").touch()
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "kmcp")
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "taxdump")


def test_sylph_ready_via_syl2db(tmp_path: Path) -> None:
    db = tmp_path / "sylph"
    db.mkdir()
    (db / "gtdb-r226-c200-dbv2.syl2db").touch()
    assert probes_ready(_by_tool(probe_databases(tmp_path)), "sylph")


def test_host_ready_via_bt2l(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    (host / "grch38.1.bt2l").touch()
    probes = _by_tool(probe_databases(tmp_path))
    assert probes["host"].ready
    assert probes["host"].path.endswith("grch38")  # reports the index prefix


def test_probes_to_dict_shape(tmp_path: Path) -> None:
    payload = probes_to_dict(tmp_path, probe_databases(tmp_path))
    assert payload["db_dir"] == str(tmp_path)
    assert set(payload["databases"]) == {
        "kraken2",
        "centrifuge",
        "kaiju",
        "metaphlan",
        "kmcp",
        "sylph",
        "taxdump",
        "host",
    }


def probes_ready(probes, tool: str) -> bool:
    probe = probes[tool]
    assert probe.ready, probe.detail
    return True
