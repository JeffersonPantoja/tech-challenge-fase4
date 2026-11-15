# Arquitetura dos pipelines

## Status e escopo

Este documento atualiza a proposta inicial para descrever a arquitetura implementada no repositório. Há dois pipelines locais e independentes em `src/`: `video_review`, para rastreamento e detecção de instrumentos, e `therapy_audio`, para extração, transcrição e análise de polaridade textual. Ambos usam Python e CLI; não há dependência funcional entre eles.

O projeto é experimental e voltado à revisão humana. Nenhum pipeline confirma anomalias clínicas, realiza diagnóstico ou deve orientar decisões clínicas ou procedimentos.

## Princípios arquiteturais

- Separar interface de linha de comando, orquestração dos casos de uso e integrações externas.
- Manter a lógica de fluxo na camada `application`; encapsular APIs de bibliotecas e serviços em `infrastructure`.
- Usar tipos e protocolos simples quando facilitarem clareza e substituição de dependências nos testes.
- Não criar camada de domínio ou abstrações sem necessidade concreta; regras simples permanecem nos casos de uso.
- Não assumir que arquivos de vídeo, pesos ou dados de entrada estejam disponíveis no repositório.

## Visão dos pacotes

```text
src/
├── video_review/
│   ├── cli.py
│   ├── models.py
│   ├── application/
│   │   ├── track_video.py
│   │   ├── dataset.py
│   │   ├── train_detector.py
│   │   ├── predict_video.py
│   │   └── first_tool_report.py
│   └── infrastructure/
│       ├── opencv_video_tracker.py
│       ├── ultralytics_trainer.py
│       ├── ultralytics_video_predictor.py
│       └── first_tool_report_adapters.py
└── therapy_audio/
    ├── cli.py
    ├── models.py
    ├── application/
    │   └── process_video.py
    └── infrastructure/
        ├── moviepy_audio_extractor.py
        ├── google_speech_transcriber.py
        ├── aws_comprehend_sentiment.py
        └── openai_segment_analyzer.py
```

Os testes automatizados ficam em `tests/`. Dados, pesos e artefatos gerados ficam sob `resources/` e `runs/`, conforme cada comando e sua configuração.

## Pipeline `video_review`

### Responsabilidades

- **`cli.py`** configura e despacha os comandos `track`, `data validate`, `data prepare`, `detector train`, `detector predict` e `detector first-tool-report`.
- **`models.py`** contém objetos de solicitação e resultado compartilhados pelo fluxo de visão.
- **`application/track_video.py`** valida a solicitação e coordena rastreamento de uma ferramenta.
- **`application/dataset.py`** valida imagens e labels, divide amostras e materializa o dataset YOLO, `data.yaml` e `split_manifest.json`.
- **`application/train_detector.py`** coordena o treino; **`application/predict_video.py`** coordena a inferência.
- **`application/first_tool_report.py`** seleciona uma detecção estável e monta relatório auditável.
- Adaptadores em **`infrastructure/`** integram OpenCV, Ultralytics e, quando explicitamente solicitado, a API de visão OpenAI.

### Fluxo

```text
CLI → caso de uso → adaptador(es) de infraestrutura → resultado/artefatos → CLI
```

O fluxo de dados típico é: selecionar manualmente uma caixa inicial, rastrear uma ferramenta, revisar as imagens e labels, validar e preparar o dataset, treinar o detector e executar inferência ou gerar relatório. O envio de frame à OpenAI em `first-tool-report` é opt-in.

### Dados e limitações

- A preparação divide imagens aleatoriamente e de forma estratificada por ferramenta (padrão 80/10/10); não agrupa por vídeo. Frames próximos podem atravessar partições, então as métricas não demonstram generalização para procedimentos independentes.
- O preparador remove e recria o destino configurado. Verificar o caminho de saída antes de executá-lo.
- Rastreamento visual não garante caixas corretas; revisar os resultados antes de usá-los no treino.
- O detector cobre as classes configuradas de instrumentos. Não há módulo validado de detecção de anomalias.

## Pipeline `therapy_audio`

### Responsabilidades

- **`cli.py`** recebe o vídeo e as opções de intervalo, saída e serviços; apresenta os resultados.
- **`models.py`** define solicitação, segmentos temporais e resultados.
- **`application/process_video.py`** coordena extração, transcrição, análise AWS e, opcionalmente, análise contextual; mantém os resultados associados aos segmentos.
- **`infrastructure/moviepy_audio_extractor.py`** extrai o áudio do intervalo solicitado.
- **`infrastructure/google_speech_transcriber.py`** segmenta próximo a pausas e transcreve em `pt-BR`.
- **`infrastructure/aws_comprehend_sentiment.py`** obtém classe e pontuações de polaridade para cada segmento.
- **`infrastructure/openai_segment_analyzer.py`** envia opcionalmente texto e resultado AWS à Responses API e solicita saída estruturada.

### Fluxo

```text
CLI → ProcessTherapyVideo → MoviePy → Google Speech → AWS Comprehend
                                             └──────→ OpenAI opcional
```

O pipeline aceita um caminho local de vídeo com áudio e executa extração, transcrição por segmentos e análise de polaridade por segmento. Salva o WAV e a transcrição com intervalos; os resultados de análise são apresentados no terminal. Artefatos recebem sufixos sequenciais para evitar sobrescrita.

### Dados e serviços externos

- O áudio é enviado ao serviço de reconhecimento Google; cada texto transcrito é enviado ao AWS Comprehend. A OpenAI só recebe os textos e resultados AWS quando a opção de análise complementar é ativada.
- Credenciais devem vir do ambiente ou do mecanismo padrão do SDK, nunca ser armazenadas no código.
- Antes de processar mídia real, verificar consentimento, autorização e condições de privacidade/uso dos serviços.
- A polaridade textual não representa intensidade emocional, avaliação psicológica ou diagnóstico. A saída OpenAI é complementar e não garante interpretação factual.

## Testes e execução

Na raiz do repositório, os pacotes são executados com `PYTHONPATH=src`. Exemplos:

```bash
PYTHONPATH=src python3 -m video_review.cli --help
PYTHONPATH=src python3 -m therapy_audio.cli --help
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Os testes devem preferir dependências substituíveis e fixtures temporárias; não usar mídia sensível nem chamar serviços externos em testes automatizados. Os fluxos com interface gráfica, GPU, vídeos reais ou serviços cloud são validações operacionais distintas dos testes unitários.

## Evolução e decisões pendentes

- Para medir generalização a procedimentos independentes, implementar e avaliar uma divisão agrupada por vídeo; não reinterpretar o split atual como tal.
- Detecção de anomalias, fases cirúrgicas e validação clínica não fazem parte da implementação atual.
- Revisar periodicamente este documento junto ao README e aos requisitos: a proposta original descrevia apenas leitura básica de vídeo e não representa o estado atual.
