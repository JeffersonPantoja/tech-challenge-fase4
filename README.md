# Harness local da wiki

CLI de pesquisa textual sobre `documentos/wiki-referencia/`. Não usa modelo de IA, rede ou dependências Python externas. PDFs são extraídos com `pdftotext` (Poppler); arquivos DOCX e notebooks são lidos pela biblioteca padrão.

O projeto inclui instruções persistentes para o OpenCode em `AGENTS.md` e uma skill de consulta à wiki em `.opencode/skills/wiki-referencia/SKILL.md`.

## Uso

```bash
python3 wiki.py indexar
python3 wiki.py buscar "reconhecimento facial"
python3 wiki.py buscar Textract -n 10
```

O índice `.wiki-index.json` é gerado no diretório do projeto. A busca reutiliza um índice válido e o cria automaticamente se estiver ausente ou em versão antiga. Execute `python3 wiki.py indexar` depois de adicionar ou alterar materiais para atualizar o índice. Resultados de PDF incluem número de página e trecho; outros formatos mostram apenas o trecho. A busca ignora palavras comuns, dá mais peso a termos específicos e descarta coincidências fracas; a pontuação é lexical, não uma medida de confiança factual. MP3 não é transcrito nesta versão.

## Testes

```bash
python3 -m unittest discover -s tests -v
```

Para extrair PDFs e obter citações por página, instale `pdftotext` (pacote Poppler) no sistema. Se não estiver disponível, a indexação continua para os demais formatos e avisa que os PDFs foram ignorados. Todos os dados permanecem locais.
