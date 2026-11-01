import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
if (ROOT / "source-snapshot").is_dir():
    ROOT = ROOT / "source-snapshot"
spec = importlib.util.spec_from_file_location("stamina_activity_generator", ROOT / "tools/build_stamina_activities.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class StaminaSelectionTests(unittest.TestCase):
    def setUp(self):
        self.source = generator.load_source(ROOT / "assets/stamina/active.yaml")
        self.cases = generator.build_cases(self.source)
        self.interface = json.loads((ROOT / "assets/interface.json").read_text(encoding="utf-8"))

    def test_insert_remove_and_reorder_invalidate_positional_selection(self):
        original = generator.activity_option_key(self.cases)
        changes = [self.cases[1:], list(reversed(self.cases)), [{"name": "新增活动关卡"}] + self.cases]
        for cases in changes:
            with self.subTest(names=[case["name"] for case in cases]):
                self.assertNotEqual(original, generator.activity_option_key(cases))

    def test_recognition_fix_keeps_existing_selection_identity(self):
        cases = copy.deepcopy(self.cases)
        cases[0]["pipeline_override"]["UnrelatedRecognition"] = {"enabled": False}
        self.assertEqual(generator.activity_option_key(self.cases), generator.activity_option_key(cases))

    def test_legacy_selector_is_replaced_and_other_settings_preserved(self):
        current = generator.activity_option_key(self.cases)
        legacy = copy.deepcopy(self.interface)
        legacy["option"][generator.OPTION_NAME] = legacy["option"].pop(current)
        task = next(t for t in legacy["task"] if t["entry"] == "DailyStaminaStart")
        task["option"] = [generator.OPTION_NAME if key == current else key for key in task["option"]]
        original_other = {k: v for k, v in legacy["option"].items() if k != generator.OPTION_NAME}
        generated = generator.update_interface(legacy, self.cases)
        self.assertNotIn(generator.OPTION_NAME, generated["option"])
        self.assertEqual(original_other, {k: v for k, v in generated["option"].items() if k != current})
        self.assertEqual(self.cases[0]["name"], generated["option"][current]["default_case"])
        self.assertEqual(self.cases, generated["option"][current]["cases"])
        self.assertEqual(generator.OPTION_NAME, generated["option"][current]["label"])
        task_after = next(t for t in generated["task"] if t["entry"] == "DailyStaminaStart")
        self.assertEqual(task["option"][1:], task_after["option"][1:])
        self.assertEqual(current, task_after["option"][0])
        self.assertEqual(generated, generator.update_interface(generated, self.cases))

    def test_placeholder_and_selection_gate_are_removed(self):
        pipeline = json.loads((ROOT / "assets/resource/pipeline/daily_stamina.json").read_text(encoding="utf-8"))
        self.assertIn("DailyStaminaOpenExpeditionFromMain", pipeline["DailyStaminaStart"]["next"])
        for name in ("DailyStaminaSelectionGate", "DailyStaminaSelectionRequired", "DailyStaminaConfiguredStart"):
            self.assertNotIn(name, pipeline)
        self.assertNotIn("请重新选择关卡", [case["name"] for case in self.cases])
        for case in self.cases:
            self.assertNotIn("DailyStaminaSelectionGate", case["pipeline_override"])

    def test_placeholder_layout_saved_index_is_invalidated(self):
        names = json.dumps([c["name"] for c in self.cases], ensure_ascii=False, separators=(",", ":"))
        previous_key = generator.OPTION_NAME + "@" + hashlib.sha256(names.encode("utf-8")).hexdigest()[:12]
        self.assertNotEqual(previous_key, generator.activity_option_key(self.cases))


if __name__ == "__main__":
    unittest.main()
