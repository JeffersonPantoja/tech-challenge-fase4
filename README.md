# Harness local da wiki

Este projeto tem dois harnesses de busca independentes, implementados junto das skills do OpenCode em `.opencode/skills/`. Não usam modelos de IA, rede ou dependências Python externas. O harness da wiki extrai PDFs com `pdftotext` (Poppler) e lê DOCX/notebooks pela biblioteca padrão; o harness de requisitos busca documentos Markdown.

O projeto inclui instruções persistentes para o OpenCode em `AGENTS.md` e skills separadas para a wiki e os requisitos.

## Uso

```bash
python3 .opencode/skills/wiki-referencia/scripts/wiki.py indexar
python3 .opencode/skills/wiki-referencia/scripts/wiki.py buscar "reconhecimento facial"
python3 .opencode/skills/wiki-referencia/scripts/wiki.py buscar Textract -n 10

python3 .opencode/skills/requisitos/scripts/requisitos.py indexar
python3 .opencode/skills/requisitos/scripts/requisitos.py buscar "revisão cirúrgica"
```

O harness da wiki salva seu índice em `.wiki-index.json`, o reutiliza entre buscas e o cria automaticamente se estiver ausente ou desatualizado. Execute o comando `indexar` da wiki após adicionar materiais. Resultados de PDF incluem página e trecho; outros formatos mostram o trecho. A busca de requisitos tem um índice próprio em `.requisitos-index.json` e o atualiza quando os Markdown mudam. Ambas as buscas são lexicais; a pontuação não é uma medida de confiança factual. MP3 não é transcrito.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

## Avaliação das skills

Conjuntos de consultas positivas e negativas para testar a descoberta automática estão em `tests/skill-activation/`. O procedimento de execução e avaliação está em `tests/skill-activation/README.md`. A avaliação de acionamento é manual porque chama o modelo configurado no OpenCode; os testes unitários não fazem chamadas a modelos.

Para extrair PDFs e obter citações por página, instale `pdftotext` (pacote Poppler) no sistema. Se não estiver disponível, a indexação da wiki continua para os demais formatos e avisa que os PDFs foram ignorados. Todos os dados permanecem locais.
