from auv_intel_digest.classify.keyword_classifier import KeywordClassifier
from auv_intel_digest.models import IntelItem, Topic


def test_classifier_matches_english_and_chinese_keywords():
    topics = [
        Topic(
            key="multi_auv_target_tracking",
            name_zh="多 AUV/UUV 协同目标跟踪",
            name_en="Multi-AUV/UUV Cooperative Target Tracking",
            enabled=True,
            weight=1.0,
            keywords={
                "zh": {
                    "positive": ["目标跟踪", "协同跟踪"],
                    "required_any": ["AUV", "水下机器人"],
                    "negative": [],
                },
                "en": {
                    "positive": ["cooperative tracking", "target tracking"],
                    "required_any": ["AUV", "underwater vehicle"],
                    "negative": [],
                },
            },
            tags=["tracking", "AUV"],
        )
    ]
    item = IntelItem(
        title="Cooperative tracking for multiple AUV systems",
        authors=[],
        source="arxiv",
        url="https://example.test/paper",
        abstract="A multi-AUV target tracking method for underwater vehicle teams.",
    )

    classified = KeywordClassifier(topics).classify(item)

    assert classified.topic == "multi_auv_target_tracking"
    assert "AUV" in classified.matched_keywords
    assert classified.score > 0
    assert "tracking" in classified.tags
