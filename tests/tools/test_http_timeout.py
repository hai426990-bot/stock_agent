"""tools/http_timeout.py 的单元测试 (无网络)。"""
import pytest
from curl_cffi.requests import Session as CurlCffiSession
from requests.sessions import Session as RequestsSession

import tools.http_timeout as ht


@pytest.fixture(autouse=True)
def _clean_guard():
    """每个测试前后还原全局 patch 状态, 避免相互影响。"""
    ht.uninstall_default_timeout()
    ht.set_default_timeout(ht.DEFAULT_TIMEOUT)
    yield
    ht.uninstall_default_timeout()
    ht.set_default_timeout(ht.DEFAULT_TIMEOUT)


def test_patch_injects_timeout_when_none():
    ht.set_default_timeout((3.0, 9.0))
    captured = {}

    def fake_original(self, method, url, **kwargs):
        captured.update(kwargs)
        return "ok"

    patched = ht._make_patch(fake_original)
    assert patched(object(), "GET", "http://x") == "ok"
    assert captured["timeout"] == (3.0, 9.0)

    captured.clear()
    assert patched(object(), "GET", "http://x", timeout=None) == "ok"
    assert captured["timeout"] == (3.0, 9.0)


def test_patch_preserves_explicit_timeout():
    captured = {}

    def fake_original(self, method, url, **kwargs):
        captured.update(kwargs)
        return "ok"

    patched = ht._make_patch(fake_original)
    patched(object(), "GET", "http://x", timeout=15)
    assert captured["timeout"] == 15


def test_install_is_idempotent_and_uninstall_restores():
    orig_requests = RequestsSession.request
    orig_curl = CurlCffiSession.request

    assert ht.install_default_timeout(verbose=False) is True
    assert RequestsSession.request is not orig_requests
    assert CurlCffiSession.request is not orig_curl
    # 二次安装为 no-op
    assert ht.install_default_timeout(verbose=False) is False

    ht.uninstall_default_timeout()
    assert RequestsSession.request is orig_requests
    assert CurlCffiSession.request is orig_curl


def test_parse_env_timeout(monkeypatch):
    monkeypatch.setenv("AKSHARE_HTTP_TIMEOUT", "3,8")
    assert ht._parse_env_timeout() == (3.0, 8.0)

    monkeypatch.setenv("AKSHARE_HTTP_TIMEOUT", "12")
    assert ht._parse_env_timeout() == (12.0, 12.0)

    monkeypatch.setenv("AKSHARE_HTTP_TIMEOUT", "abc")
    assert ht._parse_env_timeout() is None

    monkeypatch.delenv("AKSHARE_HTTP_TIMEOUT", raising=False)
    assert ht._parse_env_timeout() is None


def test_env_var_applied_on_install(monkeypatch):
    monkeypatch.setenv("AKSHARE_HTTP_TIMEOUT", "2,7")
    ht.install_default_timeout(verbose=False)
    assert ht.get_default_timeout() == (2.0, 7.0)
