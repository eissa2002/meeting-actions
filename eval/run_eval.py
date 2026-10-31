"""Manual accuracy and latency check against a real LLM provider.

Run with the LLM_* environment variables set:  python eval/run_eval.py [--delay SECONDS]
Calls the real provider (costs API usage). Not part of the pytest suite.
--delay pauses between samples to stay under provider rate limits; it is not counted in latency.
"""

import argparse
import json
import math
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import TypedDict, cast

from meeting_actions.config import ConfigError, load_settings
from meeting_actions.extractor import ExtractionError, OpenAICompatibleExtractor
from meeting_actions.models import ActionItem

SAMPLES_PATH = Path(__file__).parent / "samples.json"
TASK_SIMILARITY = 0.6

TARGET_RECALL = 0.90  # SC-001
TARGET_FABRICATION = 0.05  # SC-002
TARGET_EMPTY = 1.0  # SC-003
TARGET_P95_SECONDS = 10.0  # SC-005


class ExpectedItem(TypedDict):
    task: str
    owner: str | None
    due_date: str | None


class Sample(TypedDict):
    id: str
    notes: str
    expected: list[ExpectedItem]


def same_owner(a: str | None, b: str | None) -> bool:
    if a is None or b is None:
        return a is b
    return a.strip().lower() == b.strip().lower()


def task_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def count_matches(expected: list[ExpectedItem], returned: list[ActionItem]) -> int:
    """One-to-one greedy matching: same owner and task similarity >= TASK_SIMILARITY."""
    unused = list(returned)
    matched = 0
    for exp in expected:
        candidates = [
            (task_similarity(exp["task"], item.task), i)
            for i, item in enumerate(unused)
            if same_owner(exp["owner"], item.owner)
        ]
        best = max(candidates, default=None)
        if best is not None and best[0] >= TASK_SIMILARITY:
            unused.pop(best[1])
            matched += 1
    return matched


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay", type=float, default=0.0, help="seconds to wait between samples")
    args = parser.parse_args()

    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        return 2

    extractor = OpenAICompatibleExtractor.from_settings(settings)
    samples = cast(list[Sample], json.loads(SAMPLES_PATH.read_text(encoding="utf-8")))

    total_expected = total_returned = total_matched = 0
    empty_samples = empty_correct = 0
    latencies: list[float] = []

    for index, sample in enumerate(samples):
        if index and args.delay:
            time.sleep(args.delay)
        start = time.perf_counter()
        try:
            returned = extractor.extract(sample["notes"])
            failed = False
        except ExtractionError:
            returned = []
            failed = True
        latencies.append(time.perf_counter() - start)

        matched = count_matches(sample["expected"], returned)
        total_expected += len(sample["expected"])
        total_returned += len(returned)
        total_matched += matched
        if not sample["expected"]:
            empty_samples += 1
            if not returned and not failed:
                empty_correct += 1

        status = "FAILED" if failed else f"{matched}/{len(sample['expected'])} matched"
        print(f"{sample['id']:<28} {status:<14} returned={len(returned)}  {latencies[-1]:.1f}s")

    recall = total_matched / total_expected if total_expected else 1.0
    fabrication = (total_returned - total_matched) / total_returned if total_returned else 0.0
    empty_rate = empty_correct / empty_samples if empty_samples else 1.0
    latency_p95 = p95(latencies)

    checks = [
        ("Recall (SC-001)", f"{recall:.2f}", f">= {TARGET_RECALL:.2f}", recall >= TARGET_RECALL),
        (
            "Fabrication rate (SC-002)",
            f"{fabrication:.2f}",
            f"<= {TARGET_FABRICATION:.2f}",
            fabrication <= TARGET_FABRICATION,
        ),
        (
            "Empty list correct (SC-003)",
            f"{empty_correct}/{empty_samples}",
            "100%",
            empty_rate >= TARGET_EMPTY,
        ),
        (
            "p95 latency (SC-005)",
            f"{latency_p95:.1f}s",
            f"< {TARGET_P95_SECONDS:.0f}s",
            latency_p95 < TARGET_P95_SECONDS,
        ),
    ]

    print()
    for name, value, target, ok in checks:
        print(f"{name:<30} {value:>8}  target {target:<8} {'PASS' if ok else 'MISS'}")
    return 0 if all(ok for *_, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
