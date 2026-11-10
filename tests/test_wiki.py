import unittest
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import wiki


class SearchTests(unittest.TestCase):
    @patch("wiki.load_index")
    def test_specific_query_finds_relevant_chunks(self, load_index):
        load_index.return_value = [
            {
                "path": "textract.pdf",
                "text": "O Amazon Textract automatiza a extração de texto de documentos digitalizados.",
            },
            {"path": "audio.pdf", "text": "A transcrição converte fala em texto."},
        ]

        results = wiki.search("Textract extração de texto")

        self.assertTrue(results)
        self.assertEqual(results[0][1], "textract.pdf")

    @patch("wiki.load_index")
    def test_unrelated_query_returns_no_results(self, load_index):
        load_index.return_value = [
            {"path": "textract.pdf", "text": "O Amazon Textract extrai texto de documentos."}
        ]

        self.assertEqual(wiki.search("teletransporte quântico de dinossauros"), [])

    @patch("wiki.load_index")
    def test_one_matching_term_is_not_enough_for_multi_term_query(self, load_index):
        load_index.return_value = [
            {"path": "textract.pdf", "text": "O Amazon Textract extrai texto de documentos."}
        ]

        self.assertEqual(wiki.search("dinossauros Textract"), [])

    def test_common_words_are_ignored(self):
        self.assertEqual(wiki.terms("como fazer a busca de textos"), {"fazer", "busca", "textos"})

    @patch("wiki.load_index")
    def test_pdf_results_include_page_number(self, load_index):
        load_index.return_value = [
            {"path": "documento.pdf", "text": "", "pages": ["texto genérico", "Textract extração"]}
        ]

        results = wiki.search("Textract extração")

        self.assertTrue(results)
        self.assertEqual(results[0][1:3], ("documento.pdf", 2))


class ExtractionTests(unittest.TestCase):
    @patch("wiki.subprocess.run", side_effect=FileNotFoundError)
    def test_pdf_without_pdftotext_is_skipped(self, run):
        self.assertEqual(wiki.extract_pdf_pages(Path("missing.pdf")), [])

    def test_notebook_cells_are_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.ipynb"
            path.write_text(json.dumps({"cells": [{"source": ["hello ", "world"]}]}), encoding="utf-8")

            self.assertEqual(wiki.extract(path), "hello world")

    def test_docx_text_is_extracted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.docx"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    '<w:document xmlns:w="urn:word"><w:t>hello</w:t><w:t> world</w:t></w:document>',
                )

            self.assertEqual(wiki.extract(path), "hello\n world")


class IndexTests(unittest.TestCase):
    def test_load_index_uses_current_saved_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index_path = Path(directory) / "index.json"
            index_path.write_text(
                json.dumps({"version": wiki.INDEX_VERSION, "records": [{"path": "cached.txt", "text": "cached"}]}),
                encoding="utf-8",
            )
            with patch.object(wiki, "INDEX", index_path), patch("wiki.build_index") as build_index:
                self.assertEqual(wiki.load_index(), [{"path": "cached.txt", "text": "cached"}])
                build_index.assert_not_called()


if __name__ == "__main__":
    unittest.main()
