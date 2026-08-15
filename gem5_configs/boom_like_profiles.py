"""BOOM-like gem5 O3 profiles.

These profiles are inspired by public BOOM configurations surveyed in
notes/boom_config_survey.md. They are not cycle-accurate BOOM models.
"""

from dataclasses import dataclass, replace
from typing import Optional


@dataclass(frozen=True)
class CacheProfile:
    size: str
    assoc: int
    tag_latency: int
    data_latency: int
    response_latency: int
    mshrs: int
    tgts_per_mshr: int


@dataclass(frozen=True)
class O3Profile:
    name: str
    fetch_width: int
    decode_width: int
    rename_width: int
    dispatch_width: int
    issue_width: int
    wb_width: int
    commit_width: int
    squash_width: int
    rob_entries: int
    iq_entries: int
    lq_entries: int
    sq_entries: int
    phys_int_regs: int
    phys_float_regs: int
    phys_vec_regs: int
    l1i: CacheProfile
    l1d: CacheProfile
    l2: CacheProfile
    l3: Optional[CacheProfile] = None


MEDIUM_BOOM_LIKE = O3Profile(
    name="medium_boom_like",
    fetch_width=4,
    decode_width=4,
    rename_width=4,
    dispatch_width=4,
    issue_width=4,
    wb_width=4,
    commit_width=4,
    squash_width=4,
    rob_entries=128,
    iq_entries=64,
    lq_entries=32,
    sq_entries=32,
    phys_int_regs=128,
    phys_float_regs=128,
    phys_vec_regs=128,
    l1i=CacheProfile(
        size="32KiB",
        assoc=4,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=8,
        tgts_per_mshr=16,
    ),
    l1d=CacheProfile(
        size="32KiB",
        assoc=4,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=16,
        tgts_per_mshr=16,
    ),
    l2=CacheProfile(
        size="512KiB",
        assoc=8,
        tag_latency=12,
        data_latency=12,
        response_latency=12,
        mshrs=32,
        tgts_per_mshr=16,
    ),
)


PAPER_PF_STRIDE_LIKE = replace(
    MEDIUM_BOOM_LIKE,
    name="paper_pf_stride_like",
    l1i=CacheProfile(
        size="32KiB",
        assoc=8,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=8,
        tgts_per_mshr=16,
    ),
    l1d=CacheProfile(
        size="32KiB",
        assoc=8,
        tag_latency=2,
        data_latency=2,
        response_latency=2,
        mshrs=8,
        tgts_per_mshr=16,
    ),
    l2=CacheProfile(
        size="256KiB",
        assoc=16,
        tag_latency=15,
        data_latency=15,
        response_latency=15,
        mshrs=16,
        tgts_per_mshr=16,
    ),
    l3=CacheProfile(
        size="8MiB",
        assoc=8,
        tag_latency=20,
        data_latency=20,
        response_latency=20,
        mshrs=20,
        tgts_per_mshr=16,
    ),
)


ZIRCON_WIDTH_LIKE = replace(
    MEDIUM_BOOM_LIKE,
    name="zircon_width_like",
    fetch_width=4,
    decode_width=2,
    rename_width=2,
    dispatch_width=2,
    issue_width=5,
    wb_width=5,
    commit_width=2,
    squash_width=2,
)


ZIRCON_BOOM_MEDIUM_LIKE = replace(
    ZIRCON_WIDTH_LIKE,
    name="zircon_boom_medium_like",
    l1d=replace(ZIRCON_WIDTH_LIKE.l1d, mshrs=2),
)


ZIRCON_BLOCKING_CACHE_LIKE = replace(
    ZIRCON_WIDTH_LIKE,
    name="zircon_blocking_cache_like",
    l1i=replace(ZIRCON_WIDTH_LIKE.l1i, mshrs=1, tgts_per_mshr=1),
    l1d=replace(ZIRCON_WIDTH_LIKE.l1d, mshrs=1, tgts_per_mshr=1),
    l2=replace(ZIRCON_WIDTH_LIKE.l2, mshrs=1, tgts_per_mshr=1),
)


PROFILES = {
    "medium": MEDIUM_BOOM_LIKE,
    "medium_boom_like": MEDIUM_BOOM_LIKE,
    "paper_pf_stride_like": PAPER_PF_STRIDE_LIKE,
    "zircon_boom_medium_like": ZIRCON_BOOM_MEDIUM_LIKE,
    "zircon_blocking_cache_like": ZIRCON_BLOCKING_CACHE_LIKE,
    "zircon_width_like": ZIRCON_WIDTH_LIKE,
}


def get_profile(name: str) -> O3Profile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown profile '{name}', available: {available}") from exc
