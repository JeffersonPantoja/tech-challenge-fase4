# Instruções do projeto

## Propósito

Este projeto oferece dois harnesses de busca local independentes: um para `documentos/wiki-referencia/` e outro para `documentos/requisitos/`, cada qual com sua skill do OpenCode.

## Estrutura

- `.opencode/skills/wiki-referencia/scripts/wiki.py`: extração, indexação e busca da wiki.
- `.opencode/skills/requisitos/scripts/requisitos.py`: indexação e busca dos documentos de requisitos.
- `documentos/wiki-referencia/`: materiais de referência; preserve os arquivos originais.
- `documentos/requisitos/`: requisitos e propostas do projeto.
- `.opencode/skills/*/SKILL.md`: instruções de consulta e citação específicas de cada fonte.
- `README.md`: visão geral e instruções de uso.
- `tests/`: testes automatizados da busca e da extração.

## Uso e validação

- Wiki: `python3 .opencode/skills/wiki-referencia/scripts/wiki.py buscar "termos da consulta"`.
- Requisitos: `python3 .opencode/skills/requisitos/scripts/requisitos.py buscar "termos da consulta"`.
- Execute os testes: `python3 -m unittest discover -s tests -v`.
- Ao responder perguntas sobre a wiki, pesquise primeiro e cite os caminhos relativos exatos dos documentos consultados.
- Não envie documentos ou trechos para serviços externos.

## Convenções

- Mantenha a implementação compatível com a biblioteca padrão do Python sempre que possível.
- Não trate pontuação lexical como confiança factual; confira os trechos e o contexto no arquivo original.
- Não execute nem altere arquivos de exemplo da wiki sem solicitação explícita.
