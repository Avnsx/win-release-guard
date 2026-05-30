from __future__ import annotations

import subprocess
import time

from win11_release_guard.evaluator import evaluate_windows_update_state
from win11_release_guard.models import EvaluationStatus, LocalWindowsState, ReleasePolicy, ReleasePolicyEntry
from win11_release_guard.wua_probe import classify_update_title, query_wua_secondary
import win11_release_guard.wua_probe as wua_probe


def _policy() -> ReleasePolicy:
    return ReleasePolicy(
        broad_target_existing_devices=ReleasePolicyEntry(
            version="25H2",
            build_family=26200,
            latest_build="26200.8457",
            baseline_build="26200.8457",
            servicing_option="General Availability Channel",
        ),
        current_versions=(
            ReleasePolicyEntry(
                version="24H2",
                build_family=26100,
                latest_build="26100.8457",
                baseline_build="26100.8457",
                servicing_option="General Availability Channel",
            ),
            ReleasePolicyEntry(
                version="25H2",
                build_family=26200,
                latest_build="26200.8457",
                baseline_build="26200.8457",
                servicing_option="General Availability Channel",
            ),
        ),
        supported_build_families={26100: "24H2", 26200: "25H2"},
    )


def test_wua_unavailable_result_unchanged_with_warning():
    result = evaluate_windows_update_state(
        LocalWindowsState(current_build=26200, full_build="26200.8457"),
        _policy(),
        wua_secondary={"available": False, "warnings": ["WUA unavailable"], "errors": []},
    )

    assert result.status is EvaluationStatus.COMPLIANT
    assert any("WUA secondary probe unavailable" in warning for warning in result.warnings)


def test_wua_timeout_returns_without_hanging(monkeypatch):
    monkeypatch.setattr(wua_probe.os, "name", "nt")

    def fake_run(*args, **kwargs):
        time.sleep(0.05)
        raise subprocess.TimeoutExpired(cmd="wua", timeout=0.1)

    monkeypatch.setattr(wua_probe.subprocess, "run", fake_run)
    started = time.monotonic()

    result = query_wua_secondary("25H2", timeout_seconds=0.1)

    assert time.monotonic() - started < 0.5
    assert result["timed_out"] is True
    assert any("timed out" in warning for warning in result["warnings"])


def test_wua_no_feature_offer_while_stale_sets_silent_missing_warning():
    result = evaluate_windows_update_state(
        LocalWindowsState(current_build=26100, full_build="26100.8457"),
        _policy(),
        wua_secondary={"available": True, "service_enabled": True, "target_feature_update_offered": False},
    )

    assert result.status is EvaluationStatus.FEATURE_UPDATE_REQUIRED
    assert result.silent_feature_update_missing is True
    assert result.target_feature_update_offer_expected is True
    assert result.target_feature_update_offered is False
    assert any("Silent feature update missing" in warning for warning in result.warnings)


def test_german_and_english_update_titles_classify_correctly():
    assert classify_update_title("2026-05 Vorschauupdate (KB5089573) (26200.8524)") == "quality_preview"
    assert classify_update_title("2026-05 Preview Update for Windows 11") == "quality_preview"
    assert classify_update_title("Funktionsupdate für Windows 11, Version 25H2") == "feature_update"
    assert classify_update_title("Feature Update to Windows 11, version 25H2") == "feature_update"
    assert classify_update_title("2026-05 Kumulatives Update für Windows 11") == "quality_update"
    assert classify_update_title("2026-05 Cumulative Update for Windows 11") == "quality_update"
    assert classify_update_title("Security Intelligence-Update für Microsoft Defender Antivirus - KB2267602") == "defender_definition"
    assert classify_update_title("Security Intelligence Update for Microsoft Defender Antivirus - KB2267602") == "defender_definition"
    assert classify_update_title(".NET Framework cumulative update") == "dotnet"
    assert classify_update_title("Intel Corporation driver update") == "driver"
