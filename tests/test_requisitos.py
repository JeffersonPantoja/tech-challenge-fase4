import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".opencode/skills/requisitos/scripts"))
import requisitos


class RequirementsSearchTests(unittest.TestCase):
    @patch("requisitos.load_index")
    def test_search_returns_matching_requirement_source(self, load_index):
        load_index.return_value = [{
            "path": "documentos/requisitos/proposta.md",
            "text": "O protótipo deve sinalizar possíveis ocorrências fora do padrão para revisão humana.",
        }]

        results = requisitos.search("ocorrências revisão humana")

        self.assertTrue(results)
        self.assertEqual(results[0][1], "documentos/requisitos/proposta.md")

    @patch("requisitos.load_index")
    def test_unrelated_query_has_no_results(self, load_index):
        load_index.return_value = [{
            "path": "documentos/requisitos/proposta.md",
            "text": "O protótipo apoia a revisão humana de vídeos cirúrgicos.",
        }]

        self.assertEqual(requisitos.search("astronomia galáxias"), [])

    def test_saved_index_is_rebuilt_when_markdown_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "documentos/requisitos/item.md"
            source.parent.mkdir(parents=True)
            source.write_text("conteúdo atualizado", encoding="utf-8")
            index_path = root / ".requisitos-index.json"
            index_path.write_text(json.dumps({
                "version": requisitos.INDEX_VERSION,
                "records": [{"path": "documentos/requisitos/item.md", "text": "antigo", "mtime_ns": 0}],
            }), encoding="utf-8")

            with patch.object(requisitos, "PROJECT_ROOT", root), patch.object(requisitos, "SOURCE", source.parent), patch.object(requisitos, "INDEX", index_path):
                records = requisitos.load_index()

            self.assertEqual(records[0]["text"], "conteúdo atualizado")


if __name__ == "__main__":
    unittest.main()
