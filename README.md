# Análise de vídeo e áudio

Este repositório reúne **dois pipelines independentes**, com entradas, dependências e resultados próprios:

1. **Visão computacional — `src/video_review/`**: rastreia instrumentos em vídeos cirúrgicos, prepara imagens e caixas revisadas para YOLOv8, treina um detector e executa inferência e geração de relatórios para revisão humana.
2. **Áudio — `src/therapy_audio/`**: extrai áudio de um vídeo local, transcreve segmentos em português brasileiro e classifica a polaridade textual com AWS Comprehend. Opcionalmente, envia cada transcrição e sua classificação AWS à OpenAI para análise contextual estruturada.

O segundo pipeline pode processar o áudio do vídeo de uma sessão de terapia mencionado no contexto acadêmico do projeto, mas aceita outros vídeos locais compatíveis; não depende do pipeline visual. Ambos são experimentais: não confirmam anomalias clínicas, não diagnosticam e não devem orientar procedimentos ou decisões clínicas. Confira autorização e privacidade antes de enviar vídeos, áudios, frames ou transcrições a serviços externos.

Para detalhes sobre arquitetura, métodos, resultados, limitações e fontes dos dados, consulte o [relatório técnico dos pipelines](documentos/relatorios/relatorio-tecnico-pipelines.pdf).

## Visão geral das ferramentas

| Ferramenta | Código | Funções principais | Seções deste README |
|---|---|---|---|
| Visão computacional | `src/video_review/` | Rastreamento, preparação do dataset, treino YOLOv8, inferência e relatório da primeira detecção estável | Arquitetura, rastreamento, dataset, treino, inferência e relatório visual |
| Áudio | `src/therapy_audio/` | Extração, transcrição segmentada, polaridade por trecho com AWS Comprehend e análise OpenAI opcional | Arquitetura e pipeline de áudio |

## Pipeline de visão computacional (`video_review`)

O código da aplicação fica em `src/video_review/` e separa os casos de uso da integração com bibliotecas externas:

```text
src/video_review/
├── cli.py
├── models.py
├── application/
│   ├── track_video.py
│   ├── dataset.py
│   ├── train_detector.py
│   ├── predict_video.py
│   └── first_tool_report.py
└── infrastructure/
    ├── opencv_video_tracker.py
    ├── ultralytics_trainer.py
    ├── ultralytics_video_predictor.py
    └── first_tool_report_adapters.py
```

- **`cli.py`** define os subcomandos `track`, `data` e `detector`, seus argumentos, valores padrão e apresenta os resultados no terminal.
- **`models.py`** contém os objetos de entrada e saída usados pelos casos de uso, como caminhos de vídeo, classe, tracker e resultados.
- **`application/track_video.py`** valida a solicitação e coordena o rastreamento de uma ferramenta.
- **`application/dataset.py`** lê e valida imagens/labels, atribui amostras às partições e materializa a estrutura YOLO, `data.yaml` e `split_manifest.json`.
- **`application/train_detector.py`** coordena o treino e retorna o caminho dos melhores pesos.
- **`application/predict_video.py`** coordena a inferência em um vídeo e os artefatos produzidos.
- **`application/first_tool_report.py`** seleciona a primeira classe detectada em uma sequência consecutiva de frames e monta o relatório auditável.
- **`infrastructure/opencv_video_tracker.py`** implementa captura de vídeo, seleção da região inicial e rastreamento usando OpenCV (CSRT/KCF).
- **`infrastructure/ultralytics_trainer.py`** integra o caso de uso de treino com Ultralytics.
- **`infrastructure/ultralytics_video_predictor.py`** integra a inferência e exportação de vídeo/CSV com Ultralytics e OpenCV.
- **`infrastructure/first_tool_report_adapters.py`** lê o trecho com OpenCV, consulta o YOLO frame a frame e, somente com opt-in, envia o frame escolhido à OpenAI para descrição visual.

Essa separação mantém decisões de fluxo na camada `application` e detalhes de OpenCV/Ultralytics em `infrastructure`; `cli.py` conecta as duas.

### Fluxo e limites

1. Rastrear uma ferramenta por vez, selecionando manualmente uma região inicial.
2. Revisar imagens e caixas; corrigir ou descartar rastreamentos com deriva, oclusão ou perda do objeto.
3. Validar os rastreamentos e preparar o dataset YOLO.
4. Treinar com treino/validação e reservar teste para avaliação final.
5. Executar inferência e inspecionar vídeo anotado, CSV ou relatório da primeira detecção estável.

O rastreamento propaga visualmente uma caixa e não garante anotação correta. O split aleatório por frames pode colocar frames próximos em partições diferentes; suas métricas não demonstram generalização para procedimentos independentes. As previsões são experimentais e requerem revisão humana.

### Comandos

Os comandos abaixo são executados na raiz do repositório e usam `PYTHONPATH=src`:

```bash
PYTHONPATH=src python3 -m video_review.cli --help
PYTHONPATH=src python3 -m video_review.cli track --video resources/cholec80/videos/video01.mp4 --tool grasper --tracker CSRT
PYTHONPATH=src python3 -m video_review.cli data validate
PYTHONPATH=src python3 -m video_review.cli data prepare --seed 42
```

As etapas detalhadas de treino, avaliação, inferência e relatório estão nas seções abaixo.

## Pipeline de áudio (`therapy_audio`)

O pipeline recebe um caminho de vídeo local, extrai o intervalo de áudio solicitado, divide o áudio próximo a pausas, transcreve cada trecho em `pt-BR` e solicita ao AWS Comprehend uma classe e pontuações de polaridade por segmento. A análise contextual OpenAI é opcional e executada separadamente para cada trecho.

```text
src/therapy_audio/
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

- **`cli.py`** define o intervalo, opções dos serviços e apresentação dos resultados.
- **`models.py`** define solicitações, segmentos temporais e resultados.
- **`application/process_video.py`** coordena extração, transcrição e análises, mantendo cada resultado AWS ligado ao segmento correspondente.
- **`infrastructure/moviepy_audio_extractor.py`** extrai o áudio do período do vídeo.
- **`infrastructure/google_speech_transcriber.py`** segmenta em pausas e transcreve em `pt-BR`.
- **`infrastructure/aws_comprehend_sentiment.py`** classifica cada transcrição e retorna as pontuações AWS.
- **`infrastructure/openai_segment_analyzer.py`** envia opcionalmente texto e resultado AWS à Responses API e solicita saída estruturada por JSON Schema.

A CLI conecta o caso de uso aos adaptadores de infraestrutura. O fluxo não depende do detector de vídeo e pode ser executado sobre um vídeo local compatível com áudio.

### Comandos

```bash
PYTHONPATH=src python3 -m therapy_audio.cli --help
PYTHONPATH=src python3 -m therapy_audio.cli resources/cholec80/videos/video01.mp4 --test-seconds 60
PYTHONPATH=src python3 -m therapy_audio.cli resources/cholec80/videos/video01.mp4 \
  --start-seconds 300 --duration-seconds 120
```

O comando exige o caminho do vídeo. `--test-seconds N` processa desde o início e não pode ser combinado com `--start-seconds` nem `--duration-seconds`. Sem duração, processa do início especificado até o fim do vídeo.

Por padrão, a CLI salva o WAV extraído e a transcrição com intervalos em `resources/therapy-audio/`, usando sufixos sequenciais para não sobrescrever esses artefatos; as classificações e eventuais análises complementares são exibidas no terminal.

## Organização das pastas do projeto

```text
.
├── src/video_review/                 # Pipeline independente de visão computacional
├── src/therapy_audio/                # Pipeline independente de áudio e sentimento textual
├── resources/
│   ├── cholec80/videos/              # Vídeos de entrada (não gerados pelo pipeline)
│   ├── cholec80/tracking/            # Rastreamentos revisados, separados por ferramenta
│   ├── datasets/cholec80-yolo/       # Dataset YOLO preparado (saída recriável)
│   └── results/                      # Saídas de inferência em vídeo (padrão)
├── runs/detect/                      # Checkpoints, métricas e gráficos de treinamento
├── tests/                            # Testes automatizados
├── documentos/                       # Requisitos e materiais de referência
└── .opencode/                        # Skills e harnesses de consulta documental
```

Os diretórios de dados e resultados podem ser alterados por argumentos da CLI. Não presuma que vídeos ou modelos estejam incluídos no repositório; confira as condições de acesso e uso do Cholec80.

No pipeline visual, as pastas de rastreamento representam execuções independentes por ferramenta. A mesma origem de vídeo e índice de frame em duas pastas diferentes **não significa que sejam a mesma amostra anotada com duas ferramentas**. A preparação mantém essas amostras separadas.

## Requisitos e instalação

- Python 3.10 ou superior recomendado.
- Para `video_review`: OpenCV com suporte a trackers e interface gráfica para selecionar a região inicial, além de Ultralytics YOLOv8.
- Para `therapy_audio`: MoviePy, SpeechRecognition, pydub, boto3 e, se a análise complementar for usada, SDK OpenAI.
- Dependências Python listadas em `requirements.txt`.
- Vídeos Cholec80 disponíveis localmente; este projeto não baixa os vídeos.

Exemplo de ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Os comandos dos dois pipelines assumem execução na raiz do repositório e usam `PYTHONPATH=src`.

## Solução de problemas

### CSRT/KCF não disponível no OpenCV

Se o rastreamento falhar por ausência de `TrackerCSRT_create` ou `TrackerKCF_create`, verifique se a `.venv` tem versões conflitantes de `opencv-python` e `opencv-contrib-python`. Ambos instalam o módulo `cv2`; se estiverem em versões diferentes, o `cv2` carregado pode não incluir os trackers de contrib.

No ambiente em que o problema foi reproduzido, funcionou manter os dois pacotes na mesma versão (`4.14.0.94`) e reinstalar `opencv-contrib-python` por último:

```bash
.venv/bin/python -m pip install --force-reinstall opencv-python==4.14.0.94 opencv-contrib-python==4.14.0.94
.venv/bin/python -m pip install --force-reinstall --no-deps opencv-contrib-python==4.14.0.94
```

Valide a consistência e a presença do tracker CSRT:

```bash
.venv/bin/python -m pip check
.venv/bin/python -c "import cv2; print(cv2.__version__); print(hasattr(cv2, 'legacy') and hasattr(cv2.legacy, 'TrackerCSRT_create'))"
```

O segundo comando deve mostrar a versão do OpenCV e `True`. Esta é a configuração verificada para o ambiente descrito; se estiver usando outra versão, mantenha os dois pacotes alinhados e confirme a API disponível.

## Rastrear uma ferramenta

O comando abre o vídeo e permite selecionar manualmente a caixa inicial. A saída é organizada sob a pasta da classe e da execução:

```bash
PYTHONPATH=src python3 -m video_review.cli track \
  --video resources/cholec80/videos/video01.mp4 \
  --tool grasper \
  --tracker CSRT
```

As classes aceitas são `grasper`, `bipolar`, `hook`, `scissors`, `clipper`, `irrigator` e `specimen_bag`. O tracker também pode ser `KCF`. A raiz padrão de saída é `resources/cholec80/tracking/`; pode ser alterada com `--output-root`.

O rastreamento é uma propagação visual da caixa, não uma garantia de anotação correta. Revise as imagens e labels antes de incluí-los no treinamento.

## Validar e preparar o dataset

Validar a estrutura de origem, os labels YOLO e os IDs de classe:

```bash
PYTHONPATH=src python3 -m video_review.cli data validate
```

Preparar o dataset com a divisão aleatória estratificada por ferramenta:

```bash
PYTHONPATH=src python3 -m video_review.cli data prepare --seed 42
```

Por padrão, cada ferramenta é dividida em **80% treino, 10% validação e 10% teste**. As proporções podem ser alteradas com `--train-ratio`, `--val-ratio` e `--test-ratio`, desde que somem 1.0. A seed controla a reprodutibilidade do sorteio.

O sorteio é feito separadamente por classe de ferramenta, agregando as imagens de suas execuções de rastreamento. As amostras não são fundidas entre pastas, mesmo quando têm o mesmo vídeo e número de frame. Cada amostra preparada contém os labels YOLO do próprio rastreamento.

O destino padrão é `resources/datasets/cholec80-yolo/`. A preparação **remove e recria somente o destino configurado**; confira `--output` antes de executar se já houver dados nesse caminho. A saída contém:

```text
resources/datasets/cholec80-yolo/
├── data.yaml
├── split_manifest.json
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

O `split_manifest.json` registra a estratégia, seed, proporções, contagens por partição e ferramenta e a lista de amostras atribuídas a cada partição.

### Limite da divisão aleatória

Como as imagens vêm de vídeos, frames próximos podem acabar em partições diferentes. A estratificação equilibra a representação das ferramentas, mas **não impede vazamento temporal**; por isso, as métricas de validação/teste podem ser otimistas para imagens de vídeos já vistos. O manifesto permite auditar as alocações. Não interprete esse split como avaliação de generalização para procedimentos independentes.

## Treinar YOLOv8

```bash
PYTHONPATH=src python3 -m video_review.cli detector train \
  --dataset resources/datasets/cholec80-yolo/data.yaml \
  --model yolov8n.pt \
  --epochs 50 \
  --imgsz 640 \
  --batch 2 \
  --name cholec80-yolov8n
```

### O que significa cada parte do comando

- **`PYTHONPATH=src`**: adiciona `src/` ao caminho de importação do Python para localizar o pacote `video_review`. Essa atribuição vale somente para esse comando no shell.
- **`python3 -m video_review.cli`**: executa o módulo da interface de linha de comando da aplicação.
- **`detector train`**: seleciona a área do detector e a operação de treinamento.
- **`--dataset resources/datasets/cholec80-yolo/data.yaml`**: arquivo de configuração YOLO com os caminhos das partições e o mapeamento de classes. É o dataset preparado na etapa anterior. O padrão da CLI é esse mesmo arquivo.
- **`--model yolov8n.pt`**: checkpoint/arquitetura inicial do Ultralytics. `yolov8n` é a variante nano; o arquivo pode ser obtido pelo Ultralytics ou substituído por outro checkpoint compatível/caminho local. O padrão também é `yolov8n.pt`.
- **`--epochs 50`**: número máximo de épocas (passagens de treinamento). O padrão é 50; o treino pode terminar antes conforme as regras de parada do Ultralytics.
- **`--imgsz 640`**: tamanho de imagem usado no treino e validação. O YOLO redimensiona as imagens para esse tamanho (em geral, 640 × 640 pixels). Um valor maior pode preservar detalhes de ferramentas pequenas, mas exige mais memória e processamento; um valor menor economiza recursos, mas pode dificultar a detecção de objetos pequenos. O padrão é 640.
- **`--batch 2`**: quantidade de imagens processadas antes de cada atualização dos pesos. Um batch maior pode aproveitar melhor a GPU, mas consome mais memória; se faltar memória, reduza o valor. O padrão deste projeto é 2.
- **`--name cholec80-yolov8n`**: nome base da execução dentro do diretório de projeto. O padrão da CLI é `cholec80-yolov8n`.

Outras opções disponíveis na CLI: `--device` escolhe dispositivo (por exemplo, `0` ou `cpu`); `--project` altera a pasta pai das execuções (padrão `runs/detect`). Para consultar a ajuda atualizada:

```bash
PYTHONPATH=src python3 -m video_review.cli detector train --help
```

O treino usa as imagens de `train`; o Ultralytics usa `val` para monitorar métricas e selecionar checkpoints. **As imagens de `test` não devem ser usadas para treinar, escolher épocas ou ajustar parâmetros.**

Por padrão, os resultados são gravados em `runs/detect/cholec80-yolov8n/`, incluindo `weights/best.pt`, `weights/last.pt`, `results.csv`, gráficos e configurações. Se o nome já existir, o Ultralytics pode criar uma pasta numerada, como `cholec80-yolov8n2`; confira o caminho impresso no terminal.

## Avaliação final no teste

Depois de concluir as escolhas usando apenas treino e validação, avalie o melhor checkpoint no split de teste:

```bash
yolo detect val \
  model=runs/detect/cholec80-yolov8n/weights/best.pt \
  data=resources/datasets/cholec80-yolo/data.yaml \
  split=test
```

Use o caminho real do `best.pt` caso o Ultralytics tenha criado uma pasta numerada. Registre que essa avaliação foi feita uma única vez no conjunto reservado; se os resultados do teste forem usados para alterar o modelo ou os parâmetros, ele deixa de ser uma avaliação final independente.

## Inferência em vídeo

```bash
PYTHONPATH=src python3 -m video_review.cli detector predict \
  --video resources/cholec80/videos/video01.mp4 \
  --weights runs/detect/cholec80-yolov8n/weights/best.pt \
  --output-dir resources/results \
  --conf 0.25
```

A inferência salva um vídeo anotado e um CSV de detecções; o terminal informa os caminhos. O vídeo pode ocupar bastante espaço. As detecções são resultados experimentais para inspeção humana: ausência de detecção não prova ausência do instrumento nem identifica, por si só, um objeto anômalo.

## Primeira ferramenta detectada e relatório GPT-4o

O comando abaixo procura a primeira classe prevista em pelo menos três frames consecutivos dentro do intervalo indicado. O frame salvo é o primeiro frame dessa sequência; o relatório também informa o frame em que a sequência foi confirmada. Se mais de uma classe atingir a confirmação no mesmo frame, todas são registradas em ordem de ID de classe.

```bash
PYTHONPATH=src python3 -m video_review.cli detector first-tool-report \
  --video resources/cholec80/videos/video01.mp4 \
  --weights runs/detect/cholec80-yolov8n/weights/best.pt \
  --start-seconds 0 \
  --end-seconds 120 \
  --conf 0.25 \
  --consecutive-frames 3 \
  --output-dir resources/results
```

Sem opção adicional, a busca e os artefatos são locais e **nenhum frame é enviado à OpenAI**. Para pedir ao GPT-4o uma descrição visual do frame selecionado, configure sua chave no ambiente e use o opt-in explícito:

```bash
export OPENAI_API_KEY="sua-chave"
PYTHONPATH=src python3 -m video_review.cli detector first-tool-report \
  --video resources/cholec80/videos/video01.mp4 \
  --weights runs/detect/cholec80-yolov8n/weights/best.pt \
  --start-seconds 0 --end-seconds 120 \
  --send-frame-to-openai
```

`--send-frame-to-openai` autoriza transmitir **o frame selecionado**, não o vídeo inteiro, à API externa. O uso pode gerar custos e deve respeitar as autorizações e regras de privacidade aplicáveis. A descrição GPT-4o é conteúdo gerado por IA e não confirma a classe do YOLO nem faz avaliação clínica. A chave não é gravada nos artefatos.

### O que é enviado e solicitado ao GPT-4o

Além do frame selecionado, a chamada inclui as previsões do YOLO como contexto textual: classes, confiança e coordenadas das caixas. O frame é codificado como JPEG; imagens com lado maior que 1536 pixels são reduzidas antes do envio. O prompt pede uma descrição objetiva apenas do que está visível, orientada a um relatório técnico de revisão humana. Informa que as classes são previsões ainda não verificadas e instrui o GPT-4o a não confirmá-las nem corrigi-las, não inferir diagnóstico, anomalia clínica, intenção ou condição do paciente e não recomendar procedimentos. Também solicita que explicite incertezas e diferencie observações visuais dos metadados fornecidos.

A resposta é registrada no relatório Markdown e no JSON. Ela não é uma segunda detecção nem validação independente do YOLO; a imagem e a descrição devem ser revisadas por uma pessoa.

Opções principais: `--start-seconds` define o início (padrão 0); `--end-seconds` define o fim exclusivo (padrão: até o fim); `--conf` define confiança mínima (padrão 0,25); `--consecutive-frames` controla a confirmação consecutiva (padrão 3); `--device` escolhe dispositivo; `--output-dir` altera o destino (padrão `resources/results`); `--openai-model` define o modelo de visão (padrão `gpt-4o`). O comando falha se não houver detecção confirmada no trecho. Os artefatos incluem frame JPEG, relatório `.md` e metadados `.json`; saídas existentes com o mesmo nome não são sobrescritas.

## Classes do detector

O mapeamento de IDs usado nos labels YOLO é definido pela ordem abaixo:

| ID | Classe |
|---:|---|
| 0 | `grasper` |
| 1 | `bipolar` |
| 2 | `hook` |
| 3 | `scissors` |
| 4 | `clipper` |
| 5 | `irrigator` |
| 6 | `specimen_bag` |

Confira sempre se o ID no arquivo de label corresponde à pasta da ferramenta; o validador rejeita divergências.

## Testes

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Os testes de preparação usam fixtures temporárias e não recriam o dataset real.

## Executar o pipeline de áudio

O caminho de um vídeo local é obrigatório. Exemplo processando os primeiros 60 segundos:

```bash
PYTHONPATH=src python3 -m therapy_audio.cli resources/cholec80/videos/video01.mp4 --test-seconds 60
```

O comando extrai o WAV, cria um arquivo de transcrição com os intervalos das partes e mostra no terminal o texto, o sentimento e as pontuações AWS por segmento. Os resultados são apresentados separadamente e não combinam transcrições de segmentos diferentes.

Para analisar outro período, informe início e duração em segundos. Por exemplo, do segundo 300 ao 420:

```bash
PYTHONPATH=src python3 -m therapy_audio.cli resources/cholec80/videos/video01.mp4 \
  --start-seconds 300 --duration-seconds 120
```

Para processar desde o início por N segundos, use `--test-seconds N`; essa opção não pode ser combinada com `--start-seconds` ou `--duration-seconds`. Sem duração, o processamento segue do ponto inicial até o final do vídeo.

### Análise contextual opcional com OpenAI

Para complementar a análise de cada trecho, configure `OPENAI_API_KEY` no ambiente e acrescente `--openai-analysis`. O modelo padrão é `gpt-5.4-mini`, alterável com `--openai-model`:

```bash
PYTHONPATH=src python3 -m therapy_audio.cli resources/cholec80/videos/video01.mp4 \
  --test-seconds 60 --openai-analysis
```

Cada chamada envia à Responses API o texto de um segmento, a classe AWS (`POSITIVE`, `NEGATIVE`, `NEUTRAL` ou `MIXED`) e as pontuações das quatro classes. O prompt orienta a tratar a resposta AWS como referência, identificar expressões relevantes apenas com evidência literal, explicar o contexto, indicar sentimento complementar e não inferir diagnóstico. Structured Outputs solicita campos JSON para interpretação AWS, resumo das pontuações, termos, evidências, contexto e limitações. O schema valida a estrutura da resposta, não garante que a interpretação seja factual.

Sem `--openai-analysis`, não há chamada à OpenAI e a análise permanece apenas AWS. Com a opção ativa, há uma chamada OpenAI por segmento, além das chamadas AWS, o que pode aumentar custo e tempo de processamento. A chave é lida de `OPENAI_API_KEY`, não deve ser incluída no código ou nos argumentos do comando.

### Segmentação, arquivos e opções

O transcritor usa `SpeechRecognition` com o serviço Google em `pt-BR`; portanto, os trechos de áudio são enviados ao Google. O áudio é dividido buscando o centro de pausas detectadas: duração-alvo de 45 segundos (`--max-chunk-seconds`), limiar padrão de -35 dBFS e silêncio mínimo de 350 ms. Se não houver pausa utilizável antes do limite, o algoritmo procura uma pausa posterior; se não encontrar uma, a transcrição falha em vez de cortar no meio da fala. Os WAVs temporários dos trechos são removidos ao final; o WAV extraído completo é preservado.

Cada segmento reconhecido é enviado separadamente ao AWS Comprehend (`DetectSentiment`, idioma `pt`) e, quando solicitado, à Responses API. As credenciais AWS usam o mecanismo padrão do SDK (`boto3`). Instale as dependências com `python3 -m pip install -r requirements.txt`.

Argumentos principais:

- `--output-dir`: pasta de saída (padrão `resources/therapy-audio/`).
- `--aws-region`: região AWS (padrão `us-east-1`).
- `--start-seconds` e `--duration-seconds`: intervalo do vídeo.
- `--test-seconds`: atalho para processar desde o início por N segundos.
- `--max-chunk-seconds`: duração-alvo dos trechos de transcrição (padrão 45 segundos).
- `--openai-analysis`: habilita a análise complementar OpenAI, opt-in.
- `--openai-model`: modelo de análise OpenAI (padrão `gpt-5.4-mini`).

Os artefatos são nomeados com sufixo sequencial (`-001`, `-002` etc.) para não sobrescrever resultados existentes. O WAV completo e o arquivo `-transcricao.txt` são salvos em `resources/therapy-audio/` por padrão; os resultados da análise são apresentados no terminal.

### Privacidade e limites de interpretação

O áudio é enviado ao serviço de reconhecimento Google; o texto é enviado ao AWS Comprehend e, somente com `--openai-analysis`, também à OpenAI. Antes de processar gravações, verifique autorização, privacidade, retenção e termos aplicáveis. As pontuações AWS expressam confiança entre classes de polaridade textual, não intensidade emocional. Nem AWS nem GPT produzem, neste pipeline, diagnóstico ou avaliação clínica; a análise é experimental e requer revisão humana. Os testes automatizados usam mocks e não enviam gravações reais aos serviços externos.

## Materiais e ferramentas documentais

Os harnesses locais de busca da wiki e dos requisitos são auxiliares e não fazem parte da arquitetura `video_review`. A implementação e as instruções deles ficam sob `.opencode/`:

```bash
python3 .opencode/skills/wiki-referencia/scripts/wiki.py buscar "termos da consulta"
python3 .opencode/skills/requisitos/scripts/requisitos.py buscar "termos da consulta"
```

Consulte os documentos em `documentos/requisitos/` e `documentos/wiki-referencia/` para contexto e fontes. As buscas lexicais não substituem a leitura do documento original.
