from streamlit.testing.v1 import AppTest


def test_app_runs_end_to_end_with_fake_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("HACKKIT_CACHE_DIR", str(tmp_path / "cache"))
    app = AppTest.from_file("../app/streamlit_app.py", default_timeout=30).run()
    assert not app.exception
    app.button(key="run").click().run()
    assert not app.exception
    assert any("add up to" in w.value for w in app.warning)
