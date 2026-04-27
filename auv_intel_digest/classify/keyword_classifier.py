from __future__ import annotations

from auv_intel_digest.models import IntelItem, Topic


class KeywordClassifier:
    def __init__(self, topics: list[Topic]) -> None:
        self.topics = [topic for topic in topics if topic.enabled]

    def classify(self, item: IntelItem) -> IntelItem:
        haystack = " ".join(
            part
            for part in [item.title, item.abstract or "", item.snippet or "", " ".join(item.tags)]
            if part
        ).lower()

        best_topic: Topic | None = None
        best_score = 0.0
        best_matches: list[str] = []

        for topic in self.topics:
            score, matches, blocked = self._score_topic(topic, haystack)
            if blocked:
                continue
            weighted_score = score * topic.weight
            if weighted_score > best_score:
                best_topic = topic
                best_score = weighted_score
                best_matches = matches

        if best_topic:
            item.topic = best_topic.key
            item.matched_keywords = best_matches
            item.tags = sorted(set(item.tags + best_topic.tags))
            item.score = min(1.0, round(best_score, 4))
            item.reason = self._reason(best_topic, best_matches)
        return item

    def _score_topic(self, topic: Topic, haystack: str) -> tuple[float, list[str], bool]:
        matches: list[str] = []
        required_terms: list[str] = []
        negative_terms: list[str] = []
        positive_terms: list[str] = []

        for lang_config in topic.keywords.values():
            required_terms.extend(lang_config.get("required_any", []))
            negative_terms.extend(lang_config.get("negative", []))
            positive_terms.extend(lang_config.get("positive", []))

        for term in negative_terms:
            if term and term.lower() in haystack:
                return 0.0, [], True

        required_matches = [term for term in required_terms if term and term.lower() in haystack]
        if required_terms and not required_matches:
            return 0.0, [], True
        matches.extend(required_matches)

        positive_matches = [term for term in positive_terms if term and term.lower() in haystack]
        matches.extend(positive_matches)

        unique_matches = list(dict.fromkeys(matches))
        if not unique_matches:
            return 0.0, [], True

        score = 0.35 + 0.1 * min(len(required_matches), 3) + 0.08 * min(len(positive_matches), 5)
        return min(score, 1.0), unique_matches, False

    @staticmethod
    def _reason(topic: Topic, matches: list[str]) -> str:
        keywords = "、".join(matches[:8])
        return f"归入“{topic.name_zh}”：命中关键词 {keywords}。"
