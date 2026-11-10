#!/usr/bin/env python3
"""Busca local nos documentos de requisitos, independente da wiki de referência."""

import argparse
from collections import Counter
import json
import math
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[4]
SOURCE = PROJECT_ROOT / "documentos" / "requisitos"
INDEX = PROJECT_ROOT / ".requisitos-index.json"
INDEX_VERSION = 1
MIN_SCORE = 0.5
STOP_WORDS = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos",
    "e", "em", "entre", "o", "os", "ou", "para", "por", "que", "se", "um", "uma",
    "the", "and", "of", "to", "in", "on", "is", "for", "with",
}


def terms(text):
    return {
        term for term in re.findall(r"[\wÀ-ÿ]+", text.lower())
        if len(term) > 1 and term not in STOP_WORDS
    }


def build_index():
    if not SOURCE.is_dir():
        raise SystemExit(f"Diretório de requisitos não encontrado: {SOURCE}")
    records = []
    for path in sorted(SOURCE.rglob("*.md")):
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            records.append({
                "path": str(path.relative_to(PROJECT_ROOT)),
                "text": text,
                "mtime_ns": path.stat().st_mtime_ns,
            })
    INDEX.write_text(
        json.dumps({"version": INDEX_VERSION, "records": records}, ensure_ascii=False),
        encoding="utf-8",
    )
    return records


def load_index():
    try:
        payload = json.loads(INDEX.read_text(encoding="utf-8"))
        records = payload.get("records", [])
        if payload.get("version") != INDEX_VERSION or not isinstance(records, list):
            return build_index()
        for record in records:
            source_path = PROJECT_ROOT / record["path"]
            if not source_path.is_file() or source_path.stat().st_mtime_ns != record.get("mtime_ns"):
                return build_index()
        return records
    except (OSError, json.JSONDecodeError, AttributeError, KeyError, TypeError):
        return build_index()


def chunks(text, size=800, overlap=120):
    words = text.split()
    for start in range(0, len(words), size - overlap):
        yield " ".join(words[start:start + size])


def search(query, limit=5):
    query_terms = terms(query)
    if not query_terms:
        return []
    candidates = [
        (record["path"], number, text, terms(text))
        for record in load_index()
        for number, text in enumerate(chunks(record["text"]), 1)
    ]
    frequencies = Counter(
        term for _, _, _, chunk_terms in candidates for term in query_terms & chunk_terms
    )
    if not any(frequencies.values()):
        return []
    weights = {
        term: 1 + math.log((len(candidates) + 1) / (frequencies[term] + 1))
        for term in query_terms
    }
    total_weight = sum(weights.values())
    minimum_matches = min(2, len(query_terms))
    results = []
    for path, number, text, chunk_terms in candidates:
        matched = query_terms & chunk_terms
        score = sum(weights[term] for term in matched) / total_weight
        if len(matched) >= minimum_matches and score >= MIN_SCORE:
            results.append((score, path, number, text))
    return sorted(results, key=lambda result: result[0], reverse=True)[:max(1, limit)]


def main():
    parser = argparse.ArgumentParser(description="Pesquisa local nos documentos de requisitos.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("indexar", help="Atualiza o índice dos documentos Markdown")
    buscar = subparsers.add_parser("buscar", help="Busca nos documentos de requisitos")
    buscar.add_argument("consulta", nargs="+", help="Palavras ou frase para pesquisar")
    buscar.add_argument("-n", "--limite", type=int, default=5, help="Quantidade máxima de trechos")
    args = parser.parse_args()
    if args.command == "indexar":
        records = build_index()
        print(f"Indexados {len(records)} documentos de requisitos em {INDEX.name}.")
        return
    results = search(" ".join(args.consulta), args.limite)
    if not results:
        print("Nenhum trecho correspondente encontrado nos requisitos.")
        return
    for score, path, number, text in results:
        print(f"\n[{score:.0%}] {path} — trecho {number}\n{text[:1200]}")


if __name__ == "__main__":
    main()
