# Instruções do projeto

## Propósito

Este projeto oferece uma CLI de busca local para os materiais em `documentos/wiki-referencia/`, além de uma skill do OpenCode para orientar consultas à wiki.

## Estrutura

- `wiki.py`: extração, indexação e busca textual local.
- `documentos/wiki-referencia/`: materiais de referência; preserve os arquivos originais.
- `.opencode/skills/wiki-referencia/SKILL.md`: fluxo para consultar fontes e citá-las em respostas.
- `README.md`: visão geral e instruções de uso.
- `tests/`: testes automatizados da busca e da extração.

## Uso e validação

- Indexe: `python3 wiki.py indexar`.
- Pesquise: `python3 wiki.py buscar "termos da consulta"`.
- Execute os testes: `python3 -m unittest discover -s tests -v`.
- Ao responder perguntas sobre a wiki, pesquise primeiro e cite os caminhos relativos exatos dos documentos consultados.
- Não envie documentos ou trechos para serviços externos.

## Convenções

- Mantenha a implementação compatível com a biblioteca padrão do Python sempre que possível.
- Não trate pontuação lexical como confiança factual; confira os trechos e o contexto no arquivo original.
- Não execute nem altere arquivos de exemplo da wiki sem solicitação explícita.
