"""Scan metrics, matching the bars in docs/PROTOTYPE_PLAN.md section 2.

Definitions
  found                a truth spine has a read with a similar title (the scanner saw and read it)
  candidate recall@3   of the found spines, how many have the true work among the top 3 candidates
  auto-accept precision of reads decided AUTO, how many are correct (a hallucinated read counts as wrong)
  cost per correct book total spend divided by spines that were found and had the right candidate on top
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from booked.catalog import Catalog, CatalogWork
from booked.matching import Decision, MatchResult, Thresholds, match, title_similarity

from .cloud import ScanResult
from .truth import TruthSpine

ALIGN_THRESHOLD = 0.6  # a read counts as the truth spine if the titles are at least this similar
CORRECT_TITLE = 0.85


def is_correct(truth: TruthSpine, work: CatalogWork) -> bool:
    if truth.work_id:
        return truth.work_id == work.id
    best = max((title_similarity(truth.title, t) for t in work.all_titles()), default=0.0)
    return best >= CORRECT_TITLE


@dataclass
class Bucket:
    truth: int = 0
    found: int = 0
    candidate_hits: int = 0
    top1_hits: int = 0
    auto: int = 0
    auto_correct: int = 0

    @property
    def spine_recall(self) -> float:
        return self.found / self.truth if self.truth else 0.0

    @property
    def candidate_recall(self) -> float:
        return self.candidate_hits / self.found if self.found else 0.0

    @property
    def auto_precision(self) -> float:
        return self.auto_correct / self.auto if self.auto else 0.0


@dataclass
class Report:
    by_language: dict[str, Bucket] = field(default_factory=dict)
    overall: Bucket = field(default_factory=Bucket)
    photos: int = 0
    failed_photos: int = 0
    total_cost_usd: float = 0.0
    mean_latency_s: float = 0.0
    p90_latency_s: float = 0.0
    hallucinated_auto: int = 0
    unreadable_truth: int = 0

    @property
    def cost_per_photo(self) -> float:
        return self.total_cost_usd / self.photos if self.photos else 0.0

    @property
    def cost_per_correct_book(self) -> float:
        return self.total_cost_usd / self.overall.top1_hits if self.overall.top1_hits else 0.0

    @property
    def cost_per_three_photo_onboarding(self) -> float:
        return 3 * self.cost_per_photo

    def to_markdown(self) -> str:
        def row(name: str, b: Bucket) -> str:
            return (
                f"| {name} | {b.truth} | {b.spine_recall:.0%} | {b.candidate_recall:.0%} "
                f"| {b.auto_precision:.0%} ({b.auto_correct}/{b.auto}) |"
            )

        lines = [
            "| language | spines | read | candidate recall@3 | auto-accept precision |",
            "|---|---|---|---|---|",
            *(row(lang or "?", b) for lang, b in sorted(self.by_language.items())),
            row("**all**", self.overall),
            "",
            f"photos: {self.photos} (failed: {self.failed_photos}), unreadable spines in truth: {self.unreadable_truth}",
            f"hallucinated auto-accepts: {self.hallucinated_auto}",
            f"cost: ${self.total_cost_usd:.4f} total, ${self.cost_per_photo:.4f} per photo, "
            f"${self.cost_per_three_photo_onboarding:.4f} per 3-photo onboarding, "
            f"${self.cost_per_correct_book:.4f} per correct book",
            f"latency: mean {self.mean_latency_s:.1f}s, p90 {self.p90_latency_s:.1f}s",
        ]
        return "\n".join(lines)


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(pct * (len(ordered) - 1))))]


def evaluate(
    truth: list[TruthSpine],
    results: list[ScanResult],
    catalog: Catalog,
    *,
    thresholds: Thresholds = Thresholds(),
) -> Report:
    report = Report(photos=len(results))
    by_photo_truth: dict[str, list[TruthSpine]] = defaultdict(list)
    for spine in truth:
        by_photo_truth[spine.photo].append(spine)

    latencies: list[float] = []
    for res in results:
        report.total_cost_usd += res.cost_usd
        if res.error:
            report.failed_photos += 1
        latencies.append(res.latency_s)

        readable = [t for t in by_photo_truth.get(res.photo, []) if not t.unreadable]
        report.unreadable_truth += sum(1 for t in by_photo_truth.get(res.photo, []) if t.unreadable)
        matches: list[MatchResult] = [match(r, catalog, thresholds=thresholds) for r in res.spine_reads()]

        # Greedy one-to-one alignment of truth spines to reads by title similarity.
        pairs = sorted(
            (
                (title_similarity(t.title, m.read.title), ti, mi)
                for ti, t in enumerate(readable)
                for mi, m in enumerate(matches)
            ),
            reverse=True,
        )
        truth_to_match: dict[int, int] = {}
        used_matches: set[int] = set()
        for sim, ti, mi in pairs:
            if sim < ALIGN_THRESHOLD:
                break
            if ti in truth_to_match or mi in used_matches:
                continue
            truth_to_match[ti] = mi
            used_matches.add(mi)

        for ti, t in enumerate(readable):
            buckets = [report.overall, report.by_language.setdefault(t.language, Bucket())]
            for b in buckets:
                b.truth += 1
            mi = truth_to_match.get(ti)
            if mi is None:
                continue
            m = matches[mi]
            hit3 = any(is_correct(t, c.work) for c in m.candidates)
            hit1 = bool(m.top and is_correct(t, m.top.work))
            for b in buckets:
                b.found += 1
                b.candidate_hits += hit3
                b.top1_hits += hit1
                if m.decision is Decision.AUTO:
                    b.auto += 1
                    b.auto_correct += hit1

        # AUTO decisions on reads that match no truth spine are hallucinations: wrong by definition.
        for mi, m in enumerate(matches):
            if mi not in used_matches and m.decision is Decision.AUTO:
                report.hallucinated_auto += 1
                report.overall.auto += 1

    report.mean_latency_s = sum(latencies) / len(latencies) if latencies else 0.0
    report.p90_latency_s = _percentile(latencies, 0.9)
    return report
