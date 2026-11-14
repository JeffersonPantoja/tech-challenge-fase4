# Protótipo de revisão de vídeos cirúrgicos

Aplicação experimental para rastrear instrumentos em vídeos de colecistectomia, preparar imagens e caixas revisadas para YOLOv8, treinar um detector e executar inferência para apoiar revisão humana. Não confirma anomalias clínicas, não diagnostica e não deve orientar procedimentos ou decisões clínicas.

## Arquitetura da implementação `video_review`

O código da aplicação fica em `src/video_review/` e separa os casos de uso da integração com bibliotecas externas:

```text
src/video_review/
├── cli.py
├── models.py
├── application/
│   ├── track_video.py
│   ├── dataset.py
│   ├── train_detector.py
│   └── predict_video.py
└── infrastructure/
    ├── opencv_video_tracker.py
    ├── ultralytics_trainer.py
    └── ultralytics_video_predictor.py
```

- **`cli.py`** define os subcomandos `track`, `data` e `detector`, seus argumentos, valores padrão e apresenta os resultados no terminal.
- **`models.py`** contém os objetos de entrada e saída usados pelos casos de uso, como caminhos de vídeo, classe, tracker e resultados.
- **`application/track_video.py`** valida a solicitação e coordena o rastreamento de uma ferramenta.
- **`application/dataset.py`** lê e valida imagens/labels, atribui amostras às partições e materializa a estrutura YOLO, `data.yaml` e `split_manifest.json`.
- **`application/train_detector.py`** coordena o treino e retorna o caminho dos melhores pesos.
- **`application/predict_video.py`** coordena a inferência em um vídeo e os artefatos produzidos.
- **`infrastructure/opencv_video_tracker.py`** implementa captura de vídeo, seleção da região inicial e rastreamento usando OpenCV (CSRT/KCF).
- **`infrastructure/ultralytics_trainer.py`** integra o caso de uso de treino com Ultralytics.
- **`infrastructure/ultralytics_video_predictor.py`** integra a inferência e exportação de vídeo/CSV com Ultralytics e OpenCV.

Essa separação mantém decisões de fluxo na camada `application` e detalhes de OpenCV/Ultralytics em `infrastructure`; `cli.py` conecta as duas.

## Organização das pastas do projeto

```text
.
├── src/video_review/                 # Implementação do pipeline de visão computacional
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

## Fluxo atual

1. Rastrear **uma ferramenta por vez** em um vídeo, escolhendo manualmente uma região inicial.
2. Revisar as imagens e caixas produzidas pelo rastreador; corrigir ou descartar caixas com deriva, oclusão ou perda do objeto.
3. Validar os rastreamentos e preparar o dataset YOLO.
4. Treinar o detector usando treino e validação. O conjunto de teste fica reservado para avaliação final.
5. Executar inferência em vídeos e inspecionar o vídeo anotado e o CSV de detecções.

As pastas de rastreamento representam execuções independentes por ferramenta. A mesma origem de vídeo e índice de frame em duas pastas diferentes **não significa que sejam a mesma amostra anotada com duas ferramentas**. A preparação mantém essas amostras separadas.

## Requisitos e instalação

- Python 3.10 ou superior recomendado.
- OpenCV com suporte a trackers e interface gráfica para selecionar a região inicial.
- Ultralytics YOLOv8.
- Dependências Python listadas em `requirements.txt`.
- Vídeos Cholec80 disponíveis localmente; este projeto não baixa os vídeos.

Exemplo de ambiente virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Os comandos abaixo assumem execução na raiz do repositório e usam `PYTHONPATH=src`.

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

O sorteio é feito separadamente para as imagens de cada ferramenta/rastreamento. As amostras não são fundidas entre pastas, mesmo quando têm o mesmo vídeo e número de frame. Cada amostra preparada contém os labels YOLO do próprio rastreamento.

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

## Materiais e ferramentas documentais

Os harnesses locais de busca da wiki e dos requisitos são auxiliares e não fazem parte da arquitetura `video_review`. A implementação e as instruções deles ficam sob `.opencode/`:

```bash
python3 .opencode/skills/wiki-referencia/scripts/wiki.py buscar "termos da consulta"
python3 .opencode/skills/requisitos/scripts/requisitos.py buscar "termos da consulta"
```

Consulte os documentos em `documentos/requisitos/` e `documentos/wiki-referencia/` para contexto e fontes. As buscas lexicais não substituem a leitura do documento original.
