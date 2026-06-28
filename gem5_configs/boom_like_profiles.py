"""BOOM-like gem5 O3 profiles.

These profiles are inspired by public BOOM configurations surveyed in
notes/boom_config_survey.md. They are not cycle-accurate BOOM models.
"""

from dataclasses import dataclass


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


PROFILES = {
    "medium": MEDIUM_BOOM_LIKE,
    "medium_boom_like": MEDIUM_BOOM_LIKE,
}


def get_profile(name: str) -> O3Profile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        available = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown profile '{name}', available: {available}") from exc

