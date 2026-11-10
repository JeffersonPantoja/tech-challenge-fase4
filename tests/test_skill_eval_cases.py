import json
from pathlib import Path
import unittest


CASES_DIR = Path(__file__).parent / "skill-activation"


class SkillActivationCaseTests(unittest.TestCase):
    def test_each_skill_has_balanced_positive_and_negative_cases(self):
        for filename in ("wiki-referencia.json", "requisitos.json"):
            with self.subTest(filename=filename):
                cases = json.loads((CASES_DIR / filename).read_text(encoding="utf-8"))
                positives = [case for case in cases if case["should_trigger"]]
                negatives = [case for case in cases if not case["should_trigger"]]
                self.assertEqual(len(positives), 8)
                self.assertEqual(len(negatives), 8)
                self.assertTrue(all(case.get("query", "").strip() for case in cases))
                self.assertEqual(len({case["id"] for case in cases}), len(cases))


if __name__ == "__main__":
    unittest.main()
