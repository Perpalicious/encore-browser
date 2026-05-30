"""
Load the bucket -> group mapping from buckets.yaml.

The viewer's Bat's List tab is two-level: groups → buckets → items. The group
each bucket belongs to is curated in buckets.yaml (the `group` field). The
Auction Agent does NOT emit group; the build joins it in by bucket name.

The mapping is intentionally *resilient*: bucket taxonomies evolve, and a
categorized file may carry bucket names that no longer (or don't yet) appear in
buckets.yaml. Such buckets are reported as a WARNING and treated as ungrouped
(placed in the synthetic "Other" group) rather than crashing the build.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Synthetic group for buckets present in the data but absent from buckets.yaml.
UNGROUPED = "Other"


def load_bucket_groups(buckets_yaml_path: Path) -> tuple[dict[str, str], list[str]]:
    """
    Parse buckets.yaml.

    Returns:
        (bucket_to_group, group_order)
        - bucket_to_group: {bucket_name: group} for every bucket in the file.
        - group_order: groups in first-appearance order (for stable UI ordering).
    """
    with buckets_yaml_path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    buckets: list[dict[str, Any]] = data.get("buckets") or []
    bucket_to_group: dict[str, str] = {}
    group_order: list[str] = []

    for entry in buckets:
        name = (entry or {}).get("name")
        group = (entry or {}).get("group")
        if not name:
            continue
        if not group:
            logger.warning(
                "buckets.yaml: bucket %r has no `group` field; treating as %r.",
                name, UNGROUPED,
            )
            group = UNGROUPED
        bucket_to_group[name] = group
        if group not in group_order:
            group_order.append(group)

    return bucket_to_group, group_order


def resolve_bucket_groups(
    present_buckets: set[str],
    bucket_to_group: dict[str, str],
    group_order: list[str],
) -> tuple[dict[str, str], list[str], list[str]]:
    """
    Map every bucket actually present in the bundle to a group, resiliently.

    Returns:
        (present_bucket_groups, groups_present_ordered, ungrouped_buckets)
        - present_bucket_groups: {bucket: group} covering exactly present_buckets.
          Buckets not found in buckets.yaml map to UNGROUPED ("Other").
        - groups_present_ordered: the groups that actually have buckets present,
          in buckets.yaml order, with "Other" appended last if used.
        - ungrouped_buckets: sorted list of present buckets with no buckets.yaml
          group (for the WARNING / operator report).
    """
    present_bucket_groups: dict[str, str] = {}
    ungrouped: list[str] = []

    for bucket in present_buckets:
        group = bucket_to_group.get(bucket)
        if group is None:
            present_bucket_groups[bucket] = UNGROUPED
            ungrouped.append(bucket)
        else:
            present_bucket_groups[bucket] = group

    groups_with_items = set(present_bucket_groups.values())
    groups_present_ordered = [g for g in group_order if g in groups_with_items]
    if UNGROUPED in groups_with_items and UNGROUPED not in groups_present_ordered:
        groups_present_ordered.append(UNGROUPED)

    return present_bucket_groups, groups_present_ordered, sorted(ungrouped)
