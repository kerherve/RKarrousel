"""Préréglages nommés (logique sans interface)."""
import unittest

from rkarrousel import presets


class PresetTests(unittest.TestCase):
    def test_builtin_presets_only_use_known_keys(self):
        for preset in presets.builtin_presets():
            self.assertTrue(preset.builtin)
            self.assertLessEqual(set(preset.values), set(presets.PRESET_KEYS), preset.id)

    def test_extract_keeps_only_the_look(self):
        config = {"frame_ratio": 0.02, "language": "fr", "last_dest_dir": "C:/x", "gdrive_enabled": True, "output_format": "4:5"}
        self.assertEqual(presets.extract(config), {"frame_ratio": 0.02, "output_format": "4:5"})

    def test_extract_copies_mutable_values(self):
        config = {"disabled_kinds": ["part2"]}
        extracted = presets.extract(config)
        extracted["disabled_kinds"].append("part1")
        self.assertEqual(config["disabled_kinds"], ["part2"])

    def test_save_replace_list_and_delete(self):
        config = {}
        name = presets.save_user_preset(config, "  Mon   style ", {"frame_ratio": 0.05, "language": "en"})
        self.assertEqual(name, "Mon style")
        self.assertEqual(config["presets"]["Mon style"], {"frame_ratio": 0.05})  # la langue n'y entre pas
        presets.save_user_preset(config, "Mon style", {"frame_ratio": 0.07})
        self.assertEqual([p.values["frame_ratio"] for p in presets.user_presets(config)], [0.07])
        self.assertTrue(presets.delete_user_preset(config, "Mon style"))
        self.assertFalse(presets.delete_user_preset(config, "Mon style"))
        self.assertEqual(presets.user_presets(config), [])

    def test_names_are_validated_and_trimmed(self):
        with self.assertRaises(ValueError):
            presets.clean_name("   ")
        self.assertEqual(len(presets.clean_name("x" * 100)), presets.MAX_NAME_LENGTH)

    def test_user_presets_are_sorted_case_insensitively(self):
        config = {}
        for name in ("beta", "Alpha", "gamma"):
            presets.save_user_preset(config, name, {"frame_ratio": 0.01})
        self.assertEqual([p.id for p in presets.user_presets(config)], ["Alpha", "beta", "gamma"])

    def test_all_presets_lists_builtin_first(self):
        config = {}
        presets.save_user_preset(config, "Mine", {"frame_ratio": 0.01})
        ids = [p.id for p in presets.all_presets(config)]
        self.assertEqual(ids[-1], "Mine")
        self.assertIn("classic", ids[:-1])

    def test_find_matching_recognises_a_preset_despite_float_noise_and_case(self):
        classic = dict(presets.BUILTIN_VALUES["classic"], frame_ratio=0.0200000001, border_color="#ffffff")
        self.assertEqual(presets.find_matching(classic).id, "classic")
        self.assertIsNone(presets.find_matching({"frame_ratio": 0.5}))
        self.assertIsNone(presets.find_matching({}))

    def test_a_user_preset_wins_over_a_builtin_with_the_same_values(self):
        config = dict(presets.BUILTIN_VALUES["classic"])
        presets.save_user_preset(config, "Mon classique", presets.BUILTIN_VALUES["classic"])
        self.assertEqual(presets.find_matching(config).id, "Mon classique")


if __name__ == "__main__":
    unittest.main()
