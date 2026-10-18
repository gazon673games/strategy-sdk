import tempfile
import unittest
from pathlib import Path

from editor.compiler import catalog_schema, compile_model, publish_model
from strategy_sdk import ParameterError, load_strategy
from strategy_sdk.catalog import list_strategies


class PublicCatalogTests(unittest.TestCase):
    def test_public_catalog_contains_only_a_blank_callback(self):
        self.assertIn("empty", list_strategies())
        template = next(item for item in catalog_schema()["templates"] if item["name"] == "empty")
        self.assertEqual(template["name"], "empty")

    def test_editor_exports_loadable_source_and_preserves_existing_files(self):
        template = next(item for item in catalog_schema()["templates"] if item["name"] == "empty")
        model = {
            "schema_version": 1,
            "name": "local_example",
            "version": "1",
            "template": template["name"],
            "params": template["params"],
        }
        with tempfile.TemporaryDirectory() as directory:
            result = publish_model(model, directory)
            path = Path(result["path"])
            original = path.read_bytes()
            self.assertEqual(load_strategy(path).metadata.name, "local_example")
            with self.assertRaises(FileExistsError):
                publish_model(model, directory)
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ParameterError):
                compile_model({**model, "name": "../escape"})
