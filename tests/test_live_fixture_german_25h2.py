from __future__ import annotations

from win11_release_guard.evaluator import evaluate_windows_update_state
from win11_release_guard.models import (
    BuildEvidenceSource,
    EditionScope,
    EvaluationStatus,
    InstalledBuildClassification,
    LocalWindowsState,
    ReleaseHistoryEntry,
    ReleasePolicy,
    ReleasePolicyEntry,
    ServicingChannel,
)
from win11_release_guard.wua_probe import classify_update_title


def _live_local() -> LocalWindowsState:
    return LocalWindowsState(
        product_name="Windows 10 Pro",
        edition_id="Professional",
        display_version="25H2",
        release_id="2009",
        current_build=26200,
        ubr=8524,
        full_build="26200.8524",
        installation_type="Client",
        inferred_release="25H2",
        edition_scope=EditionScope.HOME_PRO,
        servicing_channel=ServicingChannel.GENERAL_AVAILABILITY,
    )


def _live_policy(*, include_preview: bool = True) -> ReleasePolicy:
    history = [
        ReleaseHistoryEntry(
            release="25H2",
            build_family=26200,
            build="26200.8457",
            availability_date="2026-05-12",
            update_type="2026-05 B",
            update_type_letter="B",
            kb_article="KB5089549",
            servicing_option="General Availability Channel",
        )
    ]
    if include_preview:
        history.append(
            ReleaseHistoryEntry(
                release="25H2",
                build_family=26200,
                build="26200.8524",
                availability_date="2026-05-27",
                update_type="2026-05 D Preview",
                update_type_letter="D",
                preview=True,
                kb_article="KB5089573",
                servicing_option="General Availability Channel",
            )
        )
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
                version="25H2",
                build_family=26200,
                latest_build="26200.8457",
                baseline_build="26200.8457",
                servicing_option="General Availability Channel",
            ),
        ),
        release_history=tuple(history),
        supported_build_families={26200: "25H2"},
    )


def test_live_german_25h2_preview_fixture_matches_policy_row():
    result = evaluate_windows_update_state(
        _live_local(),
        _live_policy(),
        wua_secondary={
            "available": True,
            "service_enabled": True,
            "target_feature_update_offered": False,
            "available_updates": [{"title": "Security Intelligence-Update für Microsoft Defender Antivirus - KB2267602"}],
            "history": [{"title": "2026-05 Vorschauupdate (KB5089573) (26200.8524)"}],
        },
    )

    assert result.status is EvaluationStatus.COMPLIANT
    assert result.installed_release == "25H2"
    assert result.installed_build == "26200.8524"
    assert result.installed_build_origin is not None
    assert result.installed_build_origin.classification is InstalledBuildClassification.PREVIEW
    assert result.installed_build_origin.evidence_source is BuildEvidenceSource.POLICY_RELEASE_HISTORY
    assert result.installed_build_origin.kb_article == "KB5089573"
    assert "LOCAL_BUILD_IS_PREVIEW" in result.installed_build_origin.diagnostic_flags
    assert result.local_consensus is not None
    assert result.local_consensus.display_os_name == "Windows 11 Pro"
    assert "LOCAL_PRODUCT_NAME_STALE" in result.local_consensus.conflicts


def test_german_wua_preview_title_is_secondary_origin_when_policy_row_absent():
    result = evaluate_windows_update_state(
        _live_local(),
        _live_policy(include_preview=False),
        wua_secondary={
            "available": True,
            "service_enabled": True,
            "history": [{"title": "2026-05 Vorschauupdate (KB5089573) (26200.8524)"}],
        },
    )

    assert result.status is EvaluationStatus.COMPLIANT
    assert result.installed_build_origin is not None
    assert result.installed_build_origin.classification is InstalledBuildClassification.PREVIEW
    assert result.installed_build_origin.evidence_source is BuildEvidenceSource.WUA_HISTORY
    assert result.installed_build_origin.kb_article == "KB5089573"


def test_german_defender_title_is_noise_not_relevant_os_update():
    assert classify_update_title("Security Intelligence-Update für Microsoft Defender Antivirus - KB2267602") == "defender_definition"
    assert classify_update_title("Tool zum Entfernen bösartiger Software x64 - v5.124") == "security_platform"
