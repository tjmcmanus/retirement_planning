"""Tests for the Streamlit-free cache and session-state helpers."""
import subprocess
import sys
import time

import pandas as pd

import app_cache
import app_state


def test_cache_hits_ignore_underscore_args_and_apply_defaults():
    calls = []

    @app_cache.cache_data()
    def f(a, _mtime=None, k=2):
        calls.append(1)
        return a * k

    assert f(3, _mtime=1) == 6
    assert f(3, _mtime=2) == 6          # underscore arg not part of key
    assert f(a=3, k=2) == 6             # same bound arguments
    assert len(calls) == 1
    assert f(4) == 8
    assert len(calls) == 2


def test_cache_returns_copies_so_mutation_does_not_leak():
    @app_cache.cache_data()
    def df():
        return pd.DataFrame({"a": [1]})

    first = df()
    first.loc[0, "a"] = 99
    assert df().loc[0, "a"] == 1


def test_ttl_expiry_and_clear():
    calls = []

    @app_cache.cache_data(ttl=0.05)
    def f(x):
        calls.append(1)
        return x

    f(1); f(1)
    assert len(calls) == 1
    time.sleep(0.08)
    f(1)
    assert len(calls) == 2
    f.clear()
    f(1)
    assert len(calls) == 3


def test_clear_all_clears_every_cache():
    calls = []

    @app_cache.cache_data()
    def f(x):
        calls.append(x)
        return x

    @app_cache.cache_data()
    def g(x):
        calls.append(x)
        return x

    f(1); g(1)
    app_cache.clear_all()
    f(1); g(1)
    assert len(calls) == 4


def test_exceptions_are_not_cached():
    state = {"n": 0}

    @app_cache.cache_data()
    def f():
        state["n"] += 1
        if state["n"] == 1:
            raise ValueError("boom")
        return "ok"

    try:
        f()
    except ValueError:
        pass
    assert f() == "ok"


def test_session_uses_streamlit_when_loaded_and_dict_when_not():
    import streamlit as st
    assert app_state.session() is st.session_state

    # A fresh interpreter that never imports streamlit gets the plain dict.
    code = (
        "import sys, app_state\n"
        "s = app_state.session()\n"
        "s['k'] = 1\n"
        "assert app_state.session()['k'] == 1 and isinstance(s, dict)\n"
        "assert 'streamlit' not in sys.modules\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                       cwd=str(__import__("pathlib").Path(__file__).parent.parent))
    assert r.returncode == 0, r.stderr
