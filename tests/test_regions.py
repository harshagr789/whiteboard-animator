import pytest
from pydantic import ValidationError

from whiteboard_animator.regions import (
    DRAW_BUDGET,
    Box,
    Region,
    SnippetRegionPlan,
    build_narration_weighted_plan,
)


def make_region(order: int, box: Box, annotation: str) -> Region:
    return Region(
        label=f"r{order}",
        role="main_concept",
        object=f"object {order}",
        reveal_order=order,
        box=box,
        expected_visual="",
        annotation=annotation,
    )


def test_narration_weighted_plan_spans_draw_budget_in_reveal_order():
    box_a = Box(ymin=0, xmin=0, ymax=400, xmax=1000)
    box_b = Box(ymin=500, xmin=0, ymax=1000, xmax=1000)
    plan = SnippetRegionPlan(idea="idea", regions=[
        make_region(2, box_b, "bb"),
        make_region(1, box_a, "aa"),
    ])

    entries = build_narration_weighted_plan(plan, 10.0)

    assert entries[0]["boxes"] == [box_a.model_dump()]
    assert entries[1]["boxes"] == [box_b.model_dump()]
    assert entries[0]["start"] == 0.0
    assert entries[0]["end"] == entries[1]["start"]
    assert abs(entries[-1]["end"] - DRAW_BUDGET * 10.0) < 0.01


def test_narration_weighted_plan_gives_longer_phrases_longer_slots():
    box = Box(ymin=0, xmin=0, ymax=500, xmax=500)
    plan = SnippetRegionPlan(idea="idea", regions=[
        make_region(1, box, "a" * 90),
        make_region(2, box, "a" * 10),
    ])

    entries = build_narration_weighted_plan(plan, 10.0)

    slot_long = entries[0]["end"] - entries[0]["start"]
    slot_short = entries[1]["end"] - entries[1]["start"]
    assert slot_long > slot_short * 2


def test_narration_weighted_plan_without_annotations_uses_area():
    big = Box(ymin=0, xmin=0, ymax=1000, xmax=750)
    small = Box(ymin=0, xmin=800, ymax=250, xmax=1000)
    plan = SnippetRegionPlan(idea="idea", regions=[
        make_region(1, big, ""),
        make_region(2, small, ""),
    ])

    entries = build_narration_weighted_plan(plan, 10.0)

    slot_big = entries[0]["end"] - entries[0]["start"]
    slot_small = entries[1]["end"] - entries[1]["start"]
    assert slot_big > slot_small


def test_narration_weighted_plan_empty_regions_returns_none():
    plan = SnippetRegionPlan(idea="idea", regions=[])
    assert build_narration_weighted_plan(plan, 10.0) is None


def timed_region(order, start, end):
    data = make_region(order, Box(ymin=0, xmin=0, ymax=500, xmax=500), "").model_dump()
    return Region.model_validate({**data, "start": start, "end": end})


def test_explicit_cues_preserve_gaps_and_ignore_draw_budget():
    plan = SnippetRegionPlan(idea="timed", regions=[
        timed_region(2, 4, 5), timed_region(1, 1, 2),
    ])
    entries = build_narration_weighted_plan(plan, 6)
    assert [(entry["start"], entry["end"]) for entry in entries] == [(1, 2), (4, 5)]


@pytest.mark.parametrize("start,end", [
    (None, 2), (1, None), (-1, 2), (2, 1), (2, 2),
    (float("nan"), 2), (1, float("inf")),
])
def test_invalid_region_timing_is_rejected(start, end):
    with pytest.raises(ValidationError):
        timed_region(1, start, end)


def test_mixed_timed_and_untimed_regions_are_rejected():
    untimed = make_region(2, Box(ymin=500, xmin=0, ymax=1000, xmax=1000), "")
    with pytest.raises(ValidationError, match="every region"):
        SnippetRegionPlan(idea="mixed", regions=[timed_region(1, 0, 1), untimed])


@pytest.mark.parametrize("second", [(2, 0.5, 2), (2, 0, 0.5), (1, 2, 3)])
def test_overlapping_out_of_order_or_duplicate_cues_are_rejected(second):
    with pytest.raises(ValidationError):
        SnippetRegionPlan(idea="invalid", regions=[timed_region(1, 0, 1), timed_region(*second)])


def test_explicit_cue_outside_scene_is_rejected():
    plan = SnippetRegionPlan(idea="too long", regions=[timed_region(1, 1, 3)])
    with pytest.raises(ValueError, match="beyond scene duration 2s"):
        build_narration_weighted_plan(plan, 2)
