# Pipeline de áudio e análise de sentimento de sessão de terapia

## Visão geral

Este documento registra os requisitos e o estado do pipeline acadêmico em `src/therapy_audio/`. Ele processa um vídeo local, extrai sua faixa de áudio, transcreve a fala em segmentos e analisa a polaridade textual por segmento. Todo o fluxo é executado por um único comando CLI e é independente do pipeline `src/video_review/`.

## Objetivo

Manter um pipeline reproduzível, orquestrado por um único comando CLI, para:

1. Extrair o áudio do vídeo de entrada.
2. Transcrever o áudio para texto.
3. Analisar a polaridade textual de cada segmento com AWS Comprehend e, opcionalmente, gerar análise contextual estruturada com OpenAI.

## Entrada

- O CLI recebe um caminho de vídeo local por execução; o caminho não fica fixo no código. O vídeo deve estar em formato MP4, MOV, MKV, AVI ou WebM e conter faixa de áudio.
- O vídeo inicialmente previsto para execução é `resources/dataset/sessao-terapia.mp4`, obtido de [https://www.youtube.com/watch?v=VS6YMAjdGZA](https://www.youtube.com/watch?v=VS6YMAjdGZA). O diretório/caminho é configurável: o pipeline aceita outros vídeos locais compatíveis.
- O vídeo é uma demonstração de uma sessão de Terapia Cognitivo-Comportamental (TCC), conforme o título publicado no YouTube; não deve ser descrito como uma gravação clínica real sem confirmação independente.

## Fluxo implementado

1. Um único comando CLI recebe o caminho do vídeo local como argumento, inicia e coordena todas as etapas, sem exigir comandos separados para extração, transcrição e análise.
2. Extrair para WAV o intervalo solicitado do vídeo, preservando o vídeo original.
3. Segmentar o áudio próximo a pausas e transcrever os trechos em português brasileiro (`pt-BR`), salvando texto e intervalos.
4. Solicitar análise AWS Comprehend (`LanguageCode='pt'`) separadamente para cada transcrição; opcionalmente enviar texto e resultado AWS à OpenAI para análise contextual em JSON Schema.
5. Manter CLI, caso de uso e adaptadores em `src/therapy_audio/`, separado de `src/video_review/`.

## Referência de implementação

- Usar como referência os exemplos da wiki para extração da faixa de áudio de vídeo e conversão de fala em texto.
- Usar como referência o exemplo da wiki de análise de sentimento de texto.
- A transcrição deve usar reconhecimento de fala configurado para português brasileiro (`pt-BR`), conforme o exemplo `SpeechRecognition`/Google da wiki.
- A análise de sentimento deve usar a mesma API do exemplo da wiki: AWS Comprehend via `boto3`, configurada para português (`LanguageCode='pt'`). Não usar Azure Text Analytics.
- Registrar dependências, configuração de idioma e requisitos de credenciais; não incluir segredos no código. Credenciais AWS devem ser fornecidas pelo mecanismo padrão da biblioteca/ambiente.

## Saídas esperadas

- Arquivo de áudio extraído do vídeo.
- Arquivo de texto com transcrição e intervalos dos segmentos.
- Resultado AWS e pontuações associados individualmente a cada segmento, apresentados no terminal.
- Quando solicitado, análise contextual OpenAI por segmento, também apresentada no terminal; ela não é persistida como arquivo pelo fluxo atual.
- Um comando CLI documentado que recebe o caminho do vídeo e executa o fluxo completo na ordem definida.
- O comando apresenta no terminal resultados por segmento e salva o WAV e a transcrição; resultados AWS/OpenAI não são persistidos em arquivo pelo fluxo atual.

## Avaliação

- Confirmar que o áudio extraído pode ser reproduzido e corresponde ao vídeo de origem.
- Revisar manualmente a transcrição e registrar erros relevantes de reconhecimento, como palavras omitidas, pontuação ou identificação incorreta de falantes.
- Verificar se a ferramenta de sentimento aceita o idioma da transcrição e interpretar seu resultado como classificação textual, não como avaliação clínica.
- Validar que a transcrição utiliza `pt-BR` e que a chamada ao Comprehend usa o código de idioma `pt`.
- Confirmar que a execução completa pode ser iniciada por um único comando CLI.
- Confirmar que o caminho passado ao CLI é o vídeo processado e que, ao término, o resultado final é exibido no terminal.
- Manter ligação entre cada saída e o vídeo de origem.
- O código atual nomeia WAV e transcrição com sufixo sequencial e não sobrescreve artefatos existentes. Os trechos WAV temporários são removidos após a transcrição.
- `--test-seconds` processa desde o início; não pode ser combinado com `--start-seconds` nem `--duration-seconds`. Sem duração, o intervalo vai do início indicado ao fim do vídeo.
- A segmentação usa duração-alvo de 45 segundos, limiar de silêncio de -35 dBFS e silêncio mínimo de 350 ms; pode ultrapassar o alvo para evitar cortar fala e falha se não encontrar pausa utilizável.

## Limitações e segurança

- A transcrição automática pode conter erros, especialmente em fala sobreposta, pausas, ruído ou vocabulário específico.
- O pipeline não deverá inferir diagnóstico, estado clínico ou qualidade do tratamento a partir da transcrição ou do sentimento.
- Análise de sentimento mede categorias de polaridade textual conforme a ferramenta utilizada; não equivale à avaliação psicológica da pessoa nem representa necessariamente o sentido clínico da sessão.
- Áudio e transcrição podem conter informações pessoais sensíveis. O processamento deve respeitar consentimento, autorização de uso, licença e políticas de armazenamento aplicáveis.
- O áudio é enviado ao serviço Google Speech; os textos de cada segmento são enviados ao AWS Comprehend e, somente com `--openai-analysis`, também à OpenAI. Não executar sobre material real sem autorização e sem verificar as condições de privacidade e uso dos serviços.
- Preservar o vídeo original; resultados e intermediários devem ser gravados em caminhos de saída definidos, sem sobrescrever a entrada.
- As pontuações do Comprehend são confiança entre classes de polaridade textual, não intensidade emocional. A análise gerada por OpenAI é complementar, não validada factualmente nem clinicamente.

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
- Opções disponíveis incluem `--output-dir`, `--aws-region`, `--start-seconds`, `--duration-seconds`, `--test-seconds`, `--max-chunk-seconds` e `--openai-analysis`/`--openai-model`.
- O pipeline foi implementado no pacote independente `src/therapy_audio/`, com CLI, caso de uso e adaptadores de infraestrutura, mantendo separação de responsabilidades.
- Por segmento, o comando imprime transcrição, sentimento e pontuações do Comprehend; com opt-in, imprime também a análise complementar OpenAI. Ao final, informa os caminhos do WAV e da transcrição.

## Origem do vídeo

- Vídeo no YouTube: [Paulo Knapp Demonstra uma Sessão de Terapia Cognitivo Comportamental - TCC](https://www.youtube.com/watch?v=VS6YMAjdGZA).
