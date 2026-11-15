# Pipeline de áudio e análise de sentimento de sessão de terapia

## Visão geral

Proposta de um pipeline acadêmico para processar um vídeo de demonstração de sessão de terapia, obtido do YouTube e disponibilizado localmente, extrair sua faixa de áudio, transcrever a fala e realizar análise de sentimento sobre o texto transcrito. Todo o fluxo será executado por um único comando CLI. A implementação deverá aproveitar os exemplos da wiki e seguir a arquitetura existente no projeto, sem ser criada dentro de `src/video-review`.

## Objetivo

Criar scripts separados e reproduzíveis, orquestrados por um único comando CLI, para:

1. Extrair o áudio do vídeo de entrada.
2. Transcrever o áudio para texto.
3. Analisar o sentimento da transcrição.

## Entrada

- O caminho do vídeo local deve ser informado como argumento do comando CLI; não deve ficar fixo no código.
- O vídeo inicialmente previsto para execução é `resources/dataset/sessao-terapia.mp4`, obtido de [https://www.youtube.com/watch?v=VS6YMAjdGZA](https://www.youtube.com/watch?v=VS6YMAjdGZA).
- O pipeline recebe um caminho de vídeo por execução e não pressupõe outros vídeos ou datasets.
- O vídeo é uma demonstração de uma sessão de Terapia Cognitivo-Comportamental (TCC), conforme o título publicado no YouTube; não deve ser descrito como uma gravação clínica real sem confirmação independente.

## Fluxo proposto

1. Um único comando CLI recebe o caminho do vídeo local como argumento, inicia e coordena todas as etapas, sem exigir comandos separados para extração, transcrição e análise.
2. Ler o vídeo indicado no argumento CLI e extrair sua faixa de áudio para um arquivo de áudio em `resources/` ou em diretório de saída dedicado, preservando o vídeo original.
3. Transcrever o arquivo de áudio em português brasileiro (`pt-BR`), salvando a transcrição em arquivo de texto.
4. Carregar a transcrição e executar análise de sentimento, registrando a resposta produzida pela API AWS Comprehend, como no exemplo da wiki.
5. Manter as etapas em scripts próprios e a orquestração CLI em diretório diferente de `src/video-review`, de acordo com as convenções e arquitetura do projeto.

## Referência de implementação

- Usar como referência os exemplos da wiki para extração da faixa de áudio de vídeo e conversão de fala em texto.
- Usar como referência o exemplo da wiki de análise de sentimento de texto.
- A transcrição deve usar reconhecimento de fala configurado para português brasileiro (`pt-BR`), conforme o exemplo `SpeechRecognition`/Google da wiki.
- A análise de sentimento deve usar a mesma API do exemplo da wiki: AWS Comprehend via `boto3`, configurada para português (`LanguageCode='pt'`). Não usar Azure Text Analytics.
- Registrar dependências, configuração de idioma e requisitos de credenciais; não incluir segredos no código. Credenciais AWS devem ser fornecidas pelo mecanismo padrão da biblioteca/ambiente.

## Saídas esperadas

- Arquivo de áudio extraído do vídeo.
- Arquivo de texto com a transcrição.
- Resultado da análise de sentimento associado à transcrição, em formato legível e, se adequado à arquitetura do projeto, estruturado.
- Um comando CLI documentado que recebe o caminho do vídeo e executa o fluxo completo na ordem definida.
- Ao finalizar, o comando CLI deve apresentar no terminal o resultado final da análise de sentimento; pode também salvar os artefatos intermediários e resultados em arquivos.

## Avaliação

- Confirmar que o áudio extraído pode ser reproduzido e corresponde ao vídeo de origem.
- Revisar manualmente a transcrição e registrar erros relevantes de reconhecimento, como palavras omitidas, pontuação ou identificação incorreta de falantes.
- Verificar se a ferramenta de sentimento aceita o idioma da transcrição e interpretar seu resultado como classificação textual, não como avaliação clínica.
- Validar que a transcrição utiliza `pt-BR` e que a chamada ao Comprehend usa o código de idioma `pt`.
- Confirmar que a execução completa pode ser iniciada por um único comando CLI.
- Confirmar que o caminho passado ao CLI é o vídeo processado e que, ao término, o resultado final é exibido no terminal.
- Manter ligação entre cada saída e o vídeo de origem.

## Limitações e segurança

- A transcrição automática pode conter erros, especialmente em fala sobreposta, pausas, ruído ou vocabulário específico.
- O pipeline não deverá inferir diagnóstico, estado clínico ou qualidade do tratamento a partir da transcrição ou do sentimento.
- Análise de sentimento mede categorias de polaridade textual conforme a ferramenta utilizada; não equivale à avaliação psicológica da pessoa nem representa necessariamente o sentido clínico da sessão.
- Áudio e transcrição podem conter informações pessoais sensíveis. O processamento deve respeitar consentimento, autorização de uso, licença e políticas de armazenamento aplicáveis.
- Não enviar áudio, vídeo ou transcrição a serviços externos sem autorização e sem verificar as condições de privacidade e uso do serviço.
- Preservar o vídeo original; resultados e intermediários devem ser gravados em caminhos de saída definidos, sem sobrescrever a entrada.

## Critério de sucesso acadêmico

Demonstrar um pipeline organizado e reproduzível que extrai áudio, gera uma transcrição revisável e produz uma análise de sentimento documentada, explicitando limitações e sem alegar diagnóstico ou validade clínica.

## Referências da wiki

- `documentos/wiki-referencia/analise-video-audio-texto/04-Transcricao-automatica-de-audio-e-conversao-de-fala-em-texto.pdf`, especialmente páginas 4–7 e 17–21.
- `documentos/wiki-referencia/analise-video-audio-texto/codigo/Aula 4/Transcricao de Audio/transcribe_audio.py`.
- `documentos/wiki-referencia/analise-video-audio-texto/codigo/Aula 4/Transcricao de Audio/transcribe_video.py`.
- `documentos/wiki-referencia/Textract-AWS-Comprehend/codigo/analise.py`.
- `documentos/wiki-referencia/Textract-AWS-Comprehend/03-Analise-de-texto-com-AWS-Comprehend.pdf`, páginas 5–7.

## Implementação

- CLI: `PYTHONPATH=src python3 -m therapy_audio.cli caminho/do/video.mp4`.
- Opções disponíveis: `--output-dir` para definir a pasta de artefatos e `--aws-region` para selecionar a região AWS.
- O pipeline foi implementado no pacote independente `src/therapy_audio/`, com CLI, caso de uso e adaptadores de infraestrutura, mantendo separação de responsabilidades.
- O comando imprime no terminal o sentimento, as pontuações retornadas pelo Comprehend, a transcrição e os caminhos dos artefatos.

## Origem do vídeo

- Vídeo no YouTube: [Paulo Knapp Demonstra uma Sessão de Terapia Cognitivo Comportamental - TCC](https://www.youtube.com/watch?v=VS6YMAjdGZA).
