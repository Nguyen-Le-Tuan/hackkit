from streamlit.testing.v1 import AppTest


def test_app_runs_end_to_end_with_fake_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    monkeypatch.setenv("HACKKIT_CACHE_DIR", str(tmp_path / "cache"))
    app = AppTest.from_file("../app/streamlit_app.py", default_timeout=30).run()
    assert not app.exception
    # The sidebar defaults to the first feature in sorted order, which changes whenever a new
    # feature is registered. Pin the reference example so this test does not depend on that.
    feature_box = next(box for box in app.sidebar.selectbox if box.label == "Feature")
    feature_box.select("receipt").run()
    assert not app.exception
    app.button(key="run").click().run()
    assert not app.exception
    assert any("add up to" in w.value for w in app.warning)
