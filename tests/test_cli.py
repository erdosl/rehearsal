import json

import pytest

from rehearsal.cli import main


def test_configuration_command(config_path, capsys):
    assert main(["config", "validate", "--config", str(config_path)]) == 0
    result = capsys.readouterr()
    assert "offline structural checks only" in result.out
    assert result.err == ""


@pytest.mark.parametrize("format", ["human", "json"])
def test_inventory_output_is_visibly_simulated(config_path, capsys, format):
    assert (
        main(
            ["inventory", "--config", str(config_path), "--backend", "fixture", "--format", format]
        )
        == 0
    )
    result = capsys.readouterr()
    assert not result.err
    if format == "json":
        data = json.loads(result.out)
        assert data["simulated"] is True and data["backend"] == "fixture"
        assert data["source"] == "builtin:healthy"
        assert data["nodes"][0]["name"] == "sim-pve01"
    else:
        assert result.out.startswith("SIMULATED inventory")
        assert "no infrastructure was contacted" in result.out
        for text in ("sim-local-lvm", "sim-template", "sim-vmbr0", "10.00 GiB"):
            assert text in result.out


@pytest.mark.parametrize("format", ["human", "json"])
def test_simulated_error_goes_to_stderr_without_success_output(config_path, capsys, format):
    assert (
        main(
            [
                "inventory",
                "--config",
                str(config_path),
                "--backend",
                "fixture",
                "--fixture",
                "builtin:permission-denied",
                "--format",
                format,
            ]
        )
        == 3
    )
    result = capsys.readouterr()
    assert result.out == ""
    if format == "json":
        data = json.loads(result.err)
        assert data["error"]["code"] == "permission_denied"
        assert data["simulated"] is True and data["backend"] == "fixture"
    else:
        assert "SIMULATED fixture error" in result.err
        assert "permission_denied" in result.err


def test_invalid_config_reports_safe_json(config_path, capsys):
    config_path.write_text('schema_version=1\ntoken="FAKE-SECRET"')
    assert main(["config", "validate", "--config", str(config_path), "--format", "json"]) == 2
    result = capsys.readouterr()
    assert result.out == ""
    assert "FAKE-SECRET" not in result.err
    assert json.loads(result.err)["error"]["code"] == "invalid_configuration"


@pytest.mark.parametrize("extra", [[], ["--backend", "unknown"]])
def test_explicit_backend_required(config_path, capsys, extra):
    with pytest.raises(SystemExit) as error:
        main(["inventory", "--config", str(config_path), *extra])
    assert error.value.code == 2
    assert capsys.readouterr().out == ""


def test_missing_selected_fixture_cannot_look_successful(config_path, capsys):
    assert (
        main(
            [
                "inventory",
                "--config",
                str(config_path),
                "--backend",
                "fixture",
                "--fixture",
                "missing.json",
                "--format",
                "json",
            ]
        )
        == 3
    )
    result = capsys.readouterr()
    assert result.out == ""
    data = json.loads(result.err)
    assert data["simulated"] is True
    assert data["error"]["code"] == "fixture_unreadable"
