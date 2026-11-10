#!/usr/bin/env python3
"""Busca local na wiki de referência, sem serviços externos ou dependências extras."""

import argparse
from collections import Counter
import json
import math
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).parent / "documentos" / "wiki-referencia"
SUPPORTED = {".txt", ".py", ".md", ".ipynb", ".pdf", ".docx"}
INDEX = Path(__file__).parent / ".wiki-index.json"
STOP_WORDS = {
    "a", "à", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "é", "o", "os", "ou", "para", "por", "que", "se", "um", "uma",
    "the", "and", "of", "to", "in", "on", "is", "for", "with",
}
MIN_SCORE = 0.5
INDEX_VERSION = 2


def extract(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            result = subprocess.run(
                ["pdftotext", "-layout", str(path), "-"],
                capture_output=True,
                text=True,
                errors="replace",
            )
        except FileNotFoundError:
            return ""
        if result.returncode:
            return ""
        return result.stdout
    if suffix == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                root = ElementTree.fromstring(archive.read("word/document.xml"))
            return "\n".join(t.text or "" for t in root.iter() if t.tag.endswith("}t"))
        except (OSError, KeyError, zipfile.BadZipFile, ElementTree.ParseError):
            return ""
    if suffix == ".ipynb":
        try:
            notebook = json.loads(path.read_text(encoding="utf-8"))
            return "\n".join("".join(cell.get("source", [])) for cell in notebook.get("cells", []))
        except (OSError, json.JSONDecodeError):
            return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def extract_pdf_pages(path: Path):
    """Extract PDF as page-numbered text using pdftotext form-feed separators."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        return []
    if result.returncode:
        return []
    return [page.strip() for page in result.stdout.split("\f") if page.strip()]


def build_index():
    if not ROOT.is_dir():
        raise SystemExit(f"Diretório da wiki não encontrado: {ROOT}")
    pdf_tool_available = shutil.which("pdftotext") is not None
    if not pdf_tool_available and any(
        path.is_file() and path.suffix.lower() == ".pdf" for path in ROOT.rglob("*")
    ):
        print("Aviso: pdftotext não está instalado; PDFs serão ignorados.", file=sys.stderr)
    records = []
    for path in sorted(ROOT.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED:
            if path.suffix.lower() == ".pdf":
                pages = extract_pdf_pages(path)
                text = "\n".join(pages)
                record = {"path": str(path.relative_to(ROOT)), "text": text, "pages": pages}
            else:
                text = extract(path).strip()
                record = {"path": str(path.relative_to(ROOT)), "text": text}
            if text:
                records.append(record)
    payload = {"version": INDEX_VERSION, "records": records}
    INDEX.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return records


def load_index():
    """Load a current index, rebuilding it when absent, invalid, or outdated."""
    try:
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        if payload.get("version") == INDEX_VERSION and isinstance(payload.get("records"), list):
            return payload["records"]
    except (OSError, json.JSONDecodeError, AttributeError):
        pass
    return build_index()


def chunks(text, size=900, overlap=150):
    words = text.split()
    for start in range(0, len(words), size - overlap):
        yield " ".join(words[start:start + size])


def terms(value):
    return {
        term for term in re.findall(r"[\wÀ-ÿ]+", value.lower())
        if len(term) > 1 and term not in STOP_WORDS
    }


def search(query, limit=5):
    records = load_index()
    query_terms = terms(query)
    if not query_terms:
        return []
    chunk_records = []
    for record in records:
        if record.get("pages"):
            for page_number, page_text in enumerate(record["pages"], 1):
                for chunk_number, text in enumerate(chunks(page_text), 1):
                    chunk_records.append((record["path"], page_number, chunk_number, text, terms(text)))
        else:
            for chunk_number, text in enumerate(chunks(record["text"]), 1):
                chunk_records.append((record["path"], None, chunk_number, text, terms(text)))
    frequencies = Counter(
        term
        for _, _, _, _, chunk_terms in chunk_records
        for term in query_terms & chunk_terms
    )
    present_terms = {term for term in query_terms if frequencies[term] > 0}
    if not present_terms:
        return []
    # IDF aumenta o peso de termos específicos, mas mantém termos ausentes no
    # denominador para que uma única coincidência não pareça uma boa resposta.
    weights = {
        term: 1 + math.log((len(chunk_records) + 1) / (frequencies[term] + 1))
        for term in query_terms
    }
    total_weight = sum(weights.values())
    results = []
    for path, page, number, text, chunk_terms in chunk_records:
        matched = query_terms & chunk_terms
        score = sum(weights[term] for term in matched) / total_weight
        min_matches = min(2, len(query_terms))
        if len(matched) >= min_matches and score >= MIN_SCORE:
            results.append((score, path, page, number, text))
    return sorted(results, key=lambda row: row[0], reverse=True)[:limit]


def main():
    parser = argparse.ArgumentParser(description="Pesquisa local nos materiais da wiki de referência.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("indexar", help="Extrai texto e atualiza o índice local")
    query_parser = subparsers.add_parser("buscar", help="Busca termos nos materiais indexados")
    query_parser.add_argument("consulta", nargs="+", help="Palavras ou frase para pesquisar")
    query_parser.add_argument("-n", "--limite", type=int, default=5, help="Quantidade máxima de trechos")
    args = parser.parse_args()
    if args.command == "indexar":
        records = build_index()
        print(f"Indexados {len(records)} arquivos. Índice local: {INDEX.name}")
        return
    found = search(" ".join(args.consulta), max(1, args.limite))
    if not found:
        print("Nenhum trecho correspondente encontrado.")
        return
    for score, path, page, number, text in found:
        location = f"página {page}, trecho {number}" if page is not None else f"trecho {number}"
        print(f"\n[{score:.0%}] {path} — {location}\n{text[:1200]}")


if __name__ == "__main__":
    main()
