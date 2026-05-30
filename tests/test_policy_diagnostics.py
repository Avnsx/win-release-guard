from win11_release_guard.audit_probes import extract_setup_log_evidence, parse_dism_packages
from win11_release_guard.evaluator import evaluate_windows_update_state
from win11_release_guard.models import EvaluationStatus, LocalWindowsState, ReleaseHistoryEntry, ReleasePolicy, ReleasePolicyEntry
from win11_release_guard.policy_diagnostics import GENERIC_NO_OFFER_CAUSE, apply_silent_feature_update_diagnostics


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
        release_history=(
            ReleaseHistoryEntry(
                release="25H2",
                build_family=26200,
                build="26200.8457",
                update_type_letter="B",
                servicing_option="General Availability Channel",
                availability_date="2026-05-12",
            ),
        ),
        supported_build_families={26100: "24H2", 26200: "25H2"},
    )


def _silent_result():
    return evaluate_windows_update_state(
        LocalWindowsState(current_build=26100, full_build="26100.8457"),
        _policy(),
        wua_secondary={"available": True, "target_feature_update_offered": False, "service_enabled": True},
    )


def test_target_release_pin_identifies_wufb_policy_block():
    result = apply_silent_feature_update_diagnostics(
        _silent_result(),
        {
            "windows_update_policy": {
                "values": {
                    "TargetReleaseVersion": 1,
                    "TargetReleaseVersionInfo": "24H2",
                    "ProductVersion": "Windows 11",
                }
            }
        },
    )

    assert result.silent_feature_update_missing is True
    assert result.target_feature_update_offer_expected is True
    assert result.target_feature_update_offered is False
    assert "WUfB target release policy pins older release." in result.possible_causes
    assert result.policy_blocks[0]["kind"] == "target_release_pin"


def test_wsus_enabled_identifies_managed_update_source():
    result = apply_silent_feature_update_diagnostics(
        _silent_result(),
        {
            "windows_update_policy": {
                "values": {
                    "UseWUServer": 1,
                    "WUServer": "https://wsus.contoso.example",
                    "WUStatusServer": "https://wsus.contoso.example",
                }
            }
        },
    )

    assert "WSUS/SCCM managed source." in result.possible_causes
    assert any(block["kind"] == "managed_update_source" for block in result.policy_blocks)


def test_pending_reboot_identifies_pending_reboot_cause():
    result = apply_silent_feature_update_diagnostics(
        _silent_result(),
        {"pending_reboot": {"pending": True, "evidence": [{"path": "HKLM\\...\\RebootRequired"}]}},
    )

    assert "Pending reboot." in result.possible_causes
    assert any("Reboot" in action for action in result.recommended_actions)


def test_panther_rollback_identifies_failed_or_rolled_back_setup():
    evidence = extract_setup_log_evidence(
        "TargetReleaseVersion = 25H2\nSetup rollback initiated after error 0xC1900101",
        source_path=r"C:\$Windows.~BT\Sources\Rollback\setupact.log",
    )
    result = apply_silent_feature_update_diagnostics(
        _silent_result(),
        {"setup_failure_evidence": evidence},
    )

    assert "Failed or rolled-back feature update attempt." in result.possible_causes
    assert any(item["kind"] == "rollback" for item in result.setup_failure_evidence)


def test_no_evidence_reports_hold_rollout_or_wua_issue():
    result = apply_silent_feature_update_diagnostics(_silent_result(), {})

    assert GENERIC_NO_OFFER_CAUSE in result.possible_causes
    assert any("safeguard holds" in action.lower() for action in result.recommended_actions)


def test_already_on_target_wua_no_offer_has_no_silent_pending_warning():
    result = evaluate_windows_update_state(
        LocalWindowsState(current_build=26200, full_build="26200.8457"),
        _policy(),
        wua_secondary={"available": True, "target_feature_update_offered": False},
    )

    assert result.status is EvaluationStatus.COMPLIANT
    assert result.silent_feature_update_missing is False
    assert result.possible_causes == ()


def test_parse_dism_packages_extracts_kbs_and_lcu_hints():
    packages = parse_dism_packages(
        """
Package Identity : Package_for_RollupFix~31bf3856ad364e35~amd64~~26100.1.10.1
State : Installed
Release Type : Security Update
Install Time : 5/28/2026 10:00 AM

Package Identity : Package_for_KB5089549~31bf3856ad364e35~amd64~~26200.8457.1.1
State : Installed
Release Type : Update
"""
    )

    assert packages[0]["is_lcu_hint"] is True
    assert packages[1]["kb_ids"] == ["KB5089549"]
    assert packages[1]["state"] == "Installed"
