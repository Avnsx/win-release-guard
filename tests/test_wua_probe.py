import builtins
import subprocess
import sys
import time
from types import ModuleType, SimpleNamespace

from win11_release_guard import wua_probe


class ComCollection:
    def __init__(self, items):
        self._items = list(items)
        self.Count = len(self._items)

    def Item(self, index):
        return self._items[index]


class SearchResult:
    def __init__(self, updates):
        self.Updates = ComCollection(updates)


class Searcher:
    def __init__(self, updates, history):
        self._updates = updates
        self._history = history
        self.criteria = []

    def Search(self, criteria):
        self.criteria.append(criteria)
        return SearchResult(self._updates)

    def GetTotalHistoryCount(self):
        return len(self._history)

    def QueryHistory(self, start, count):
        return ComCollection(self._history[start : start + count])


class Session:
    def __init__(self, searcher):
        self._searcher = searcher
        self.ClientApplicationID = None

    def CreateUpdateSearcher(self):
        return self._searcher


class FakeWin32Client:
    def __init__(self, searcher):
        self.searcher = searcher
        self.dispatch_calls = []

    def Dispatch(self, name):
        self.dispatch_calls.append(name)
        if name == "Microsoft.Update.AutoUpdate":
            return SimpleNamespace(ServiceEnabled=True)
        if name == "Microsoft.Update.Session":
            return Session(self.searcher)
        raise ValueError(name)


def _install_fake_win32com(monkeypatch, client, event_logs=None):
    win32com = ModuleType("win32com")
    win32com.client = client
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setattr(
        wua_probe,
        "_query_event_logs",
        event_logs if event_logs is not None else (lambda *args, **kwargs: ([], [])),
    )


def test_query_wua_secondary_non_windows(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "posix")

    result = wua_probe.query_wua_secondary("25H2", use_subprocess=False)

    assert result["available"] is False
    assert result["errors"] == ["WUA only available on Windows"]


def test_query_wua_secondary_missing_win32com(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    monkeypatch.delitem(sys.modules, "win32com", raising=False)
    monkeypatch.delitem(sys.modules, "win32com.client", raising=False)
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "win32com.client":
            raise ImportError("No module named win32com")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    result = wua_probe.query_wua_secondary("25H2", use_subprocess=False)

    assert result["available"] is False
    assert result["errors"]
    assert "win32com unavailable" in result["errors"][0]


def test_query_wua_secondary_detects_target_feature_update_offer(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    update = SimpleNamespace(
        Title="Feature Update to Windows 11, version 25H2",
        KBArticleIDs=ComCollection(["5080000"]),
        Categories=ComCollection([SimpleNamespace(Name="Upgrades")]),
        Identity=SimpleNamespace(UpdateID="feature-update-id", RevisionNumber=7),
        SupportUrl="https://support.microsoft.com/help/5080000",
    )
    history_entry = SimpleNamespace(
        Title="2026-05 Cumulative Update for Windows 11 Version 25H2",
        Date="2026-05-12",
        Operation=1,
        ResultCode=2,
        HResult=0,
        UnmappedResultCode=0,
    )
    searcher = Searcher([update], [history_entry])
    client = FakeWin32Client(searcher)
    _install_fake_win32com(monkeypatch, client)

    result = wua_probe.query_wua_secondary("25H2", max_history=10, use_subprocess=False)

    assert result["available"] is True
    assert result["service_enabled"] is True
    assert result["target_feature_update_offered"] is True
    assert result["target_release_in_history"] is True
    assert result["available_updates"][0]["title"] == "Feature Update to Windows 11, version 25H2"
    assert result["available_updates"][0]["kb_ids"] == ["KB5080000"]
    assert result["available_updates"][0]["classification"] == "feature_update"
    assert result["available_updates"][0]["update_identity"] == {
        "UpdateID": "feature-update-id",
        "RevisionNumber": 7,
    }
    assert result["available_updates"][0]["support_url"] == "https://support.microsoft.com/help/5080000"
    assert result["history"][0]["mentions_target_release"] is True
    assert result["history"][0]["operation"] == 1
    assert result["history"][0]["result_code"] == 2
    assert result["history"][0]["hresult"] == 0
    assert searcher.criteria == ["IsInstalled=0 and Type='Software' and IsHidden=0"]


def test_query_wua_secondary_counts_defender_noise_but_excludes_relevant_os_updates(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    update = SimpleNamespace(
        Title="Security Intelligence-Update for Microsoft Defender Antivirus - KB2267602",
        KBArticleIDs=ComCollection(["2267602"]),
        Categories=ComCollection([SimpleNamespace(Name="Definition Updates")]),
    )
    searcher = Searcher([update], [])
    client = FakeWin32Client(searcher)
    _install_fake_win32com(monkeypatch, client)

    result = wua_probe.query_wua_secondary("25H2", max_history=10, use_subprocess=False)

    assert result["available_updates"][0]["classification"] == "defender_definition"
    assert result["noise_counts"]["defender_definition"] == 1
    assert result["relevant_os_updates"] == []


def test_query_wua_secondary_subprocess_timeout_returns_within_timeout(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")

    def fake_run(*args, **kwargs):
        time.sleep(0.05)
        raise subprocess.TimeoutExpired(cmd="wua", timeout=0.1)

    monkeypatch.setattr(wua_probe.subprocess, "run", fake_run)
    started = time.monotonic()

    result = wua_probe.query_wua_secondary("25H2", timeout_seconds=0.1)

    assert time.monotonic() - started < 0.5
    assert result["timed_out"] is True
    assert any("timed out" in warning for warning in result["warnings"])


def test_query_wua_secondary_correlates_setup_event_log_by_kb(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    history_entry = SimpleNamespace(
        Title="2026-05 Vorschauupdate (KB5089573) (26200.8524)",
        Date="2026-05-28",
        Operation=1,
        ResultCode=2,
        HResult=0,
        UnmappedResultCode=0,
    )
    searcher = Searcher([], [history_entry])
    client = FakeWin32Client(searcher)

    def event_logs(kb_ids, **kwargs):
        assert "KB5089573" in kb_ids
        return (
            [
                {
                    "log_name": "Setup",
                    "provider_name": "Microsoft-Windows-Servicing",
                    "event_id": 2,
                    "time_created": "2026-05-28T12:00:00",
                    "message": "Package install completed for KB5089573",
                    "kb_ids": ["KB5089573"],
                    "classification": "quality_preview",
                }
            ],
            [],
        )

    _install_fake_win32com(monkeypatch, client, event_logs=event_logs)

    result = wua_probe.query_wua_secondary("25H2", max_history=10, use_subprocess=False)

    assert result["history"][0]["classification"] == "quality_preview"
    assert result["correlated_event_logs"][0]["log_name"] == "Setup"
    assert result["correlated_event_logs"][0]["kb_ids"] == ["KB5089573"]


def test_query_wua_secondary_caps_relevant_os_updates(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    updates = [
        SimpleNamespace(
            Title=f"2026-05 Cumulative Update for Windows 11 Version 25H2 (KB50895{i:02d})",
            KBArticleIDs=ComCollection([f"50895{i:02d}"]),
            Categories=ComCollection([SimpleNamespace(Name="Updates")]),
        )
        for i in range(12)
    ]
    searcher = Searcher(updates, [])
    client = FakeWin32Client(searcher)
    _install_fake_win32com(monkeypatch, client)

    result = wua_probe.query_wua_secondary(
        "25H2",
        max_history=10,
        max_relevant_updates=10,
        use_subprocess=False,
    )

    assert len(result["available_updates"]) == 12
    assert len(result["relevant_os_updates"]) == 10
    assert any("truncated" in warning for warning in result["warnings"])


def test_query_wua_secondary_event_log_access_denied_becomes_warning(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")
    history_entry = SimpleNamespace(
        Title="2026-05 Vorschauupdate (KB5089573) (26200.8524)",
        Date="2026-05-28",
        Operation=1,
        ResultCode=2,
        HResult=0,
        UnmappedResultCode=0,
    )
    searcher = Searcher([], [history_entry])
    client = FakeWin32Client(searcher)

    def event_logs(*args, **kwargs):
        raise PermissionError("access denied")

    _install_fake_win32com(monkeypatch, client, event_logs=event_logs)

    result = wua_probe.query_wua_secondary("25H2", max_history=10, use_subprocess=False)

    assert any("Event log permission warning" in warning for warning in result["warnings"])
