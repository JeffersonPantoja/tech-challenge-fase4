# Protótipo acadêmico de apoio à revisão cirúrgica

## Visão geral

Este documento registra o escopo acadêmico do pipeline de visão computacional em `src/video_review/`. A implementação atual rastreia instrumentos em vídeos, prepara dados YOLO, treina um detector e gera resultados para revisão humana. O sistema não confirma anomalias clínicas, não diagnostica e não deve orientar procedimentos cirúrgicos reais.

## Objetivo

Construir e avaliar um pipeline experimental de detecção e rastreamento de instrumentos cirúrgicos, produzindo evidências auditáveis para revisão humana. A geração de candidatos por objetos desconhecidos ou ocorrências fora do padrão permanece uma investigação futura: a detecção atual não implementa nem valida detecção de anomalias.

## Base de dados

O Cholec80 contém vídeos de colecistectomias laparoscópicas, rótulos de fases cirúrgicas e anotações de presença de instrumentos. Antes da implementação, a equipe deve verificar o formato, a cobertura e a granularidade das anotações disponíveis para a versão escolhida.

As anotações de presença não equivalem necessariamente a localizações de objetos. Um detector que produza caixas delimitadoras (*bounding boxes*) requer anotações espaciais apropriadas; não se deve presumir que estejam disponíveis para todas as ferramentas e frames.

## Fluxo implementado e limites

O fluxo implementado é deliberadamente simples e segue o exemplo de rastreamento da wiki:

1. Abrir um vídeo e selecionar manualmente a caixa inicial de uma ferramenta; registrar a classe.
2. Inicializar o rastreador OpenCV (KCF ou CSRT) e propagar a caixa pelos frames.
3. Salvar imagens e labels YOLO da execução de rastreamento; revisar e corrigir ou descartar caixas com deriva, oclusão ou perda do objeto.
4. Validar as imagens, labels e IDs de classe e preparar `data.yaml` e `split_manifest.json`.
5. Treinar YOLOv8, usar validação para acompanhar o treino e manter o split de teste fora da seleção do modelo; executar inferência e inspecionar vídeo/CSV.
6. Opcionalmente, procurar a primeira classe prevista em uma sequência configurável de frames consecutivos e produzir artefatos de relatório. O envio do frame selecionado à OpenAI é opt-in.

O split implementado é aleatório e estratificado por classe/ferramenta, com padrão 80% treino, 10% validação e 10% teste. Frames próximos do mesmo vídeo podem cair em partições diferentes; portanto, essa divisão não satisfaz o requisito de avaliação independente por procedimento descrito abaixo e pode superestimar métricas. A preparação mantém execuções de rastreamento separadas, mesmo quando vídeo e frame de origem coincidem.

O Cholec80 pode ajudar a escolher frames por presença de ferramenta, mas seus rótulos binários não definem a caixa inicial nem substituem a identificação visual e a validação manual. O procedimento deve respeitar as condições de uso e citação do dataset.

## Saídas implementadas e objetivos pendentes

- Rastreamentos por ferramenta com imagens e labels YOLO para revisão.
- Dataset YOLO preparado, incluindo `data.yaml` e `split_manifest.json` com partições e amostras.
- Pesos e métricas de treino Ultralytics; vídeo anotado e CSV de detecções na inferência.
- Para `first-tool-report`, frame JPEG, relatório Markdown e metadados JSON da primeira detecção estável; descrição OpenAI somente quando solicitada explicitamente.
- Permanecem objetivos não atendidos: partição independente por vídeo/procedimento e implementação/avaliação de detecção de anomalias.

## Avaliação

- Verificar visualmente e corrigir as caixas do rastreador antes de usá-las como rótulos de treinamento.
- O código atual separa imagens aleatoriamente por ferramenta, não por vídeo/procedimento. Para afirmar generalização a procedimentos independentes, é necessário implementar e avaliar uma divisão agrupada por vídeo.
- Avaliar erros incluindo oclusão, desfoque e enquadramento incompleto; não usar o teste para selecionar épocas ou ajustar parâmetros.
- Se a etapa experimental de candidatos a revisão for implementada, avaliá-la separadamente do detector; métricas de detecção não comprovam detecção de anomalias.

## Limitações e segurança

- Uma ferramenta não detectada pode estar presente, mas ocultada, fora do enquadramento ou não reconhecida pelo modelo.
- Uma classe não prevista no dataset não deve ser automaticamente tratada como anomalia.
- Rastreamento visual propaga uma região com base na aparência/movimento; não identifica por si só a classe do objeto nem garante caixas corretas. Oclusões, movimento, deformação e mudanças de aparência podem causar deriva ou perda do rastreador.
- O vídeo com retângulos desenhados não substitui as anotações estruturadas por frame exigidas para treino do YOLOv8; coordenadas e classes precisam ser exportadas e validadas.
- A ausência de uma detecção YOLO não prova que exista um objeto desconhecido ou uma anomalia; pode ser uma falha de detecção. A saída deve ser apresentada como candidato incerto para revisão humana.
- O Cholec80 fornece rótulos binários de ferramentas a 1 fps, enquanto os vídeos são gravados a 25 fps; o alinhamento de frames e timestamps deve ser verificado. As caixas feitas ou propagadas em outros frames são novas anotações e precisam de revisão.
- A ausência de uma anotação não prova a ausência do objeto no vídeo.
- Rótulos de presença de instrumentos podem não oferecer localização espacial; a detecção por caixas depende de *bounding boxes* anotadas.
- Os resultados dependem da qualidade, cobertura e licença dos dados, bem como da distribuição dos vídeos e das condições de captura.
- O protótipo é exclusivamente acadêmico e de apoio à revisão. Não deve ser usado para diagnóstico, avaliação clínica definitiva ou decisão intraoperatória.

## Critério de sucesso acadêmico

Demonstrar um pipeline reprodutível de rastreamento e detecção de instrumentos, com saídas auditáveis para revisão humana e avaliação quantitativa de acertos e limitações, sem alegar validação clínica. A implementação atual não identifica fases cirúrgicas nem produz alertas de anomalia.

## Referências iniciais

- Dataset Cholec80 e informações de acesso: [CAMMA — Datasets](https://camma.unistra.fr/datasets/).
- Publicação associada ao Cholec80: A. P. Twinanda et al., *EndoNet: A Deep Architecture for Recognition Tasks on Laparoscopic Videos*, IEEE Transactions on Medical Imaging, 2017.
