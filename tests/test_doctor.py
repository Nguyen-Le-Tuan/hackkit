"""scripts/doctor.py must never crash and never print key values."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doctor  # noqa: E402

FAKE_KEY = "gsk_" + "Z9y8X7w6V5u4T3s2R1q0P9o8"  # not a real key


def test_doctor_survives_an_empty_path_outside_a_repo(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")
    monkeypatch.chdir(tmp_path)
    code = doctor.main(["--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert code in (0, 1)
    assert "probe failed" not in out
    assert "not a git checkout" in out and "node" in out
    assert out.rstrip().endswith("to check WebGL and fonts.")


def test_doctor_reports_keys_as_set_or_empty_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", "")
    (tmp_path / ".env").write_text(
        f"LLM_PROVIDER=groq\nGROQ_API_KEY={FAKE_KEY}\nANTHROPIC_API_KEY=\nDEMO_MODE=true\n"
    )
    doctor.main(["--repo", str(tmp_path)])
    out = capsys.readouterr().out
    assert FAKE_KEY not in out
    lines = {line.split()[1]: line for line in out.splitlines() if line[:4].strip()}
    assert "set" in lines["GROQ_API_KEY"] and lines["GROQ_API_KEY"].startswith("OK")
    assert "empty" in lines["ANTHROPIC_API_KEY"]
    assert "groq" in lines["LLM_PROVIDER"] and "true" in lines["DEMO_MODE"]


def test_missing_key_for_selected_provider_warns(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", "")
    (tmp_path / ".env").write_text("LLM_PROVIDER=anthropic\nANTHROPIC_API_KEY=\n")
    checks = {c.name: c for c in doctor.probe_env(tmp_path)}
    assert checks["ANTHROPIC_API_KEY"].status == doctor.WARN


def test_a_crashing_probe_becomes_a_warning(monkeypatch, tmp_path):
    def boom(root):
        raise RuntimeError("no such device")

    monkeypatch.setattr(doctor, "PROBES", [boom])
    checks = doctor.run_probes(tmp_path)
    assert checks[0].status == doctor.WARN and "no such device" in checks[0].detail
