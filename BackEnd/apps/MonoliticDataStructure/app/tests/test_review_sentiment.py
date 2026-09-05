import unittest


def classify(text: str) -> str:
    lowered = text.lower()
    if any(term in lowered for term in ("bueno", "excelente", "genial", "recomiendo", "perfecto", "great", "good")):
        return "positive"
    if any(term in lowered for term in ("malo", "defecto", "roto", "tarde", "poor", "bad", "broken")):
        return "negative"
    return "neutral"


class ReviewSentimentTests(unittest.TestCase):
    def test_review_batch_can_be_classified_without_ai(self):
        self.assertEqual(classify("Producto excelente, lo recomiendo"), "positive")
        self.assertEqual(classify("Llego roto y tarde"), "negative")
        self.assertEqual(classify("Cumple lo descrito"), "neutral")


if __name__ == "__main__":
    unittest.main()
