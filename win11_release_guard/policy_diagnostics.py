from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

from .models import EvaluationResult, EvaluationStatus


GENERIC_NO_OFFER_CAUSE = "Safeguard hold, staged rollout delay, unsupported/blocked hardware, or WUA service/cache issue."


def _release_key(release: str | None) -> tuple[int, int]:
    if not release or len(release) != 4:
        return (-1, -1)
    try:
        return int(release[:2]), int(release[-1])
    except ValueError:
        return (-1, -1)


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "enabled"}


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _wua_target_offered(wua_secondary: Mapping[str, Any] | None) -> bool | None:
    if not isinstance(wua_secondary, Mapping):
        return None
    if "target_feature_update_offered" in wua_secondary:
        return bool(wua_secondary.get("target_feature_update_offered"))
    if "target_release_offered" in wua_secondary:
        return bool(wua_secondary.get("target_release_offered"))
    return None


def should_apply_silent_feature_update_diagnostics(result: EvaluationResult) -> bool:
    if result.status is not EvaluationStatus.FEATURE_UPDATE_REQUIRED:
        return False
    if not isinstance(result.wua_secondary, Mapping):
        return False
    if result.wua_secondary.get("available") is not True:
        return False
    if _wua_target_offered(result.wua_secondary) is not False:
        return False
    if result.target and result.installed_release:
        return _release_key(result.installed_release) < _release_key(result.target.version)
    return True


def _policy_values(audit_diagnostics: Mapping[str, Any]) -> Mapping[str, Any]:
    policy = audit_diagnostics.get("windows_update_policy")
    if not isinstance(policy, Mapping):
        return {}
    values = policy.get("values")
    return values if isinstance(values, Mapping) else {}


def _policy_blocks(policy_values: Mapping[str, Any], target_release: str | None) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    target_info = str(policy_values.get("TargetReleaseVersionInfo") or "").upper()
    if _truthy(policy_values.get("TargetReleaseVersion")) and target_info and target_release and target_info != target_release.upper():
        blocks.append(
            {
                "kind": "target_release_pin",
                "description": "WUfB target release policy pins older release.",
                "TargetReleaseVersion": policy_values.get("TargetReleaseVersion"),
                "TargetReleaseVersionInfo": policy_values.get("TargetReleaseVersionInfo"),
                "ProductVersion": policy_values.get("ProductVersion"),
                "target_release": target_release,
            }
        )
    if _truthy(policy_values.get("UseWUServer")) or policy_values.get("WUServer") or policy_values.get("WUStatusServer"):
        blocks.append(
            {
                "kind": "managed_update_source",
                "description": "WSUS/SCCM managed update source is configured.",
                "UseWUServer": policy_values.get("UseWUServer"),
                "WUServer": policy_values.get("WUServer"),
                "WUStatusServer": policy_values.get("WUStatusServer"),
            }
        )
    if (
        _truthy(policy_values.get("DeferFeatureUpdates"))
        or _int_value(policy_values.get("DeferFeatureUpdatesPeriodInDays")) > 0
        or policy_values.get("BranchReadinessLevel") not in (None, "")
    ):
        blocks.append(
            {
                "kind": "feature_update_deferral",
                "description": "Feature update deferral policy is configured.",
                "DeferFeatureUpdates": policy_values.get("DeferFeatureUpdates"),
                "DeferFeatureUpdatesPeriodInDays": policy_values.get("DeferFeatureUpdatesPeriodInDays"),
                "BranchReadinessLevel": policy_values.get("BranchReadinessLevel"),
            }
        )
    if _truthy(policy_values.get("DisableOSUpgrade")):
        blocks.append(
            {
                "kind": "disable_os_upgrade",
                "description": "DisableOSUpgrade policy is configured.",
                "DisableOSUpgrade": policy_values.get("DisableOSUpgrade"),
            }
        )
    return blocks


def _pending_reboot(audit_diagnostics: Mapping[str, Any]) -> Mapping[str, Any]:
    pending = audit_diagnostics.get("pending_reboot")
    return pending if isinstance(pending, Mapping) else {"pending": False, "evidence": [], "errors": []}


def _setup_failure_evidence(audit_diagnostics: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence = audit_diagnostics.get("setup_failure_evidence")
    if isinstance(evidence, list):
        return [dict(item) for item in evidence if isinstance(item, Mapping)]
    panther = audit_diagnostics.get("panther_logs")
    if not isinstance(panther, Mapping):
        return []
    panther_evidence = panther.get("setup_failure_evidence", [])
    return [dict(item) for item in panther_evidence if isinstance(item, Mapping)]


def _wua_health(wua_secondary: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(wua_secondary, Mapping):
        return {"available": False, "target_feature_update_offered": None}
    return {
        "available": wua_secondary.get("available"),
        "service_enabled": wua_secondary.get("service_enabled"),
        "target_feature_update_offered": _wua_target_offered(wua_secondary),
        "target_release_in_history": wua_secondary.get("target_release_in_history"),
        "timed_out": wua_secondary.get("timed_out", False),
        "warnings": list(wua_secondary.get("warnings", [])),
        "errors": list(wua_secondary.get("errors", [])),
    }


def _causes_and_actions(
    *,
    policy_blocks: list[dict[str, Any]],
    pending_reboot: Mapping[str, Any],
    setup_failure_evidence: list[dict[str, Any]],
    wua_health: Mapping[str, Any],
) -> tuple[list[str], list[str]]:
    causes: list[str] = []
    actions: list[str] = []
    block_kinds = {block.get("kind") for block in policy_blocks}

    if "target_release_pin" in block_kinds:
        causes.append("WUfB target release policy pins older release.")
        actions.append("Review TargetReleaseVersionInfo and set it to the approved target release or remove the pin.")
    if "managed_update_source" in block_kinds:
        causes.append("WSUS/SCCM managed source.")
        actions.append("Verify the managed update source has a deployment or approval for the target feature update.")
    if "feature_update_deferral" in block_kinds:
        causes.append("Feature update deferral.")
        actions.append("Review feature update deferral days and branch readiness policy.")
    if "disable_os_upgrade" in block_kinds:
        causes.append("OS upgrade disabled by policy.")
        actions.append("Remove or correct DisableOSUpgrade if this device should receive feature updates.")
    if pending_reboot.get("pending"):
        causes.append("Pending reboot.")
        actions.append("Reboot the device, then rerun the release guard check.")
    failed_or_rolled_back = [
        item for item in setup_failure_evidence if item.get("kind") in {"setup_failure", "rollback"}
    ]
    if failed_or_rolled_back:
        causes.append("Failed or rolled-back feature update attempt.")
        actions.append("Inspect Panther setup logs and rollback evidence before retrying the feature update.")
    if wua_health.get("service_enabled") is False or wua_health.get("timed_out") or wua_health.get("errors"):
        causes.append("WUA service/cache issue.")
        actions.append("Check Windows Update service health and cache state; do not override the policy verdict.")
    if not causes:
        causes.append(GENERIC_NO_OFFER_CAUSE)
        actions.append("Check safeguard holds, rollout eligibility, WUA health, and hardware compatibility.")

    return list(dict.fromkeys(causes)), list(dict.fromkeys(actions))


def build_silent_feature_update_diagnostics(
    result: EvaluationResult,
    audit_diagnostics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    audit = audit_diagnostics or {}
    target_release = result.target.version if result.target else None
    policy_blocks = _policy_blocks(_policy_values(audit), target_release)
    pending_reboot = _pending_reboot(audit)
    setup_failure_evidence = _setup_failure_evidence(audit)
    wua_health = _wua_health(result.wua_secondary)
    possible_causes, recommended_actions = _causes_and_actions(
        policy_blocks=policy_blocks,
        pending_reboot=pending_reboot,
        setup_failure_evidence=setup_failure_evidence,
        wua_health=wua_health,
    )
    return {
        "silent_feature_update_missing": True,
        "target_feature_update_offer_expected": True,
        "target_feature_update_offered": False,
        "possible_causes": possible_causes,
        "recommended_actions": recommended_actions,
        "policy_blocks": policy_blocks,
        "wua_health": wua_health,
        "setup_failure_evidence": setup_failure_evidence,
        "audit_diagnostics": dict(audit),
    }


def apply_silent_feature_update_diagnostics(
    result: EvaluationResult,
    audit_diagnostics: Mapping[str, Any] | None = None,
) -> EvaluationResult:
    if not should_apply_silent_feature_update_diagnostics(result):
        return result
    diagnostics = build_silent_feature_update_diagnostics(result, audit_diagnostics)
    details = dict(result.details)
    details["silent_feature_update_missing"] = diagnostics
    warnings = list(result.warnings)
    warning = "Silent feature update missing: target feature update is expected by policy but WUA did not offer it."
    if warning not in warnings:
        warnings.append(warning)
    return replace(
        result,
        silent_feature_update_missing=True,
        target_feature_update_offer_expected=True,
        target_feature_update_offered=False,
        possible_causes=tuple(diagnostics["possible_causes"]),
        recommended_actions=tuple(diagnostics["recommended_actions"]),
        policy_blocks=tuple(diagnostics["policy_blocks"]),
        wua_health=diagnostics["wua_health"],
        setup_failure_evidence=tuple(diagnostics["setup_failure_evidence"]),
        details=details,
        warnings=tuple(warnings),
        notes=tuple(dict.fromkeys((*result.notes, warning))),
    )


__all__ = [
    "GENERIC_NO_OFFER_CAUSE",
    "apply_silent_feature_update_diagnostics",
    "build_silent_feature_update_diagnostics",
    "should_apply_silent_feature_update_diagnostics",
]
