# Protótipo acadêmico de apoio à revisão cirúrgica

## Visão geral

Proposta de um protótipo acadêmico que analisa vídeos de colecistectomia laparoscópica do dataset Cholec80 para sinalizar **possíveis ocorrências fora do padrão** e facilitar a revisão posterior por uma pessoa. O sistema não confirma anomalias clínicas, não diagnostica e não deve orientar procedimentos cirúrgicos reais.

## Objetivo

Construir e avaliar um pipeline experimental que use detecção e rastreamento de instrumentos cirúrgicos para destacar frames ou intervalos que mereçam revisão humana. Em uma etapa posterior, investigar se objetos que não correspondam às classes de instrumentos conhecidas podem gerar candidatos a revisão. Isso não equivale a detectar uma anomalia clínica: o protótipo não confirma anomalias, não diagnostica e não orienta procedimentos reais.

## Base de dados

O Cholec80 contém vídeos de colecistectomias laparoscópicas, rótulos de fases cirúrgicas e anotações de presença de instrumentos. Antes da implementação, a equipe deve verificar o formato, a cobertura e a granularidade das anotações disponíveis para a versão escolhida.

As anotações de presença não equivalem necessariamente a localizações de objetos. Um detector que produza caixas delimitadoras (*bounding boxes*) requer anotações espaciais apropriadas; não se deve presumir que estejam disponíveis para todas as ferramentas e frames.

## Fluxo proposto

O fluxo inicial será deliberadamente simples, seguindo o exemplo de rastreamento da wiki:

1. Abrir um vídeo e selecionar manualmente, em um frame inicial, a caixa da ferramenta a rastrear; registrar a classe da ferramenta.
2. Inicializar um rastreador visual do OpenCV (KCF ou CSRT) com esse frame e caixa, e acompanhar a região nos frames seguintes do vídeo.
3. Salvar um vídeo de saída com as caixas desenhadas e, junto dele, os dados das caixas por frame em formato estruturado. O vídeo anotado serve para inspeção; os dados estruturados das coordenadas/classes são necessários para formar rótulos de treinamento.
4. Revisar manualmente o resultado rastreado, corrigindo ou descartando caixas quando houver deriva, oclusão ou perda do objeto. Só caixas validadas poderão compor os dados de treinamento.
5. Separar os vídeos por procedimento em treino, validação e teste, sem distribuir frames do mesmo vídeo entre partições. Treinar/ajustar o YOLOv8 com frames e caixas validadas; avaliar em vídeos mantidos fora do treino.
6. Como etapa posterior e experimental, investigar candidatos a revisão com base em baixa confiança ou evidência não explicada pelas classes conhecidas. Uma detecção ausente ou objeto não reconhecido não será considerado automaticamente uma anomalia; será apresentado para revisão humana.

O Cholec80 pode ajudar a escolher frames por presença de ferramenta, mas seus rótulos binários não definem a caixa inicial nem substituem a identificação visual e a validação manual. O procedimento deve respeitar as condições de uso e citação do dataset.

## Saídas esperadas

- Vídeo de saída com caixas rastreadas, para inspeção manual.
- Coordenadas, classe, frame e timestamp das caixas em formato estruturado, mantendo a ligação com o vídeo de origem.
- Conjunto de frames e caixas revisados, separado por vídeo/procedimento em treino, validação e teste, para treinamento e avaliação do YOLOv8.
- Em etapa posterior, lista de candidatos a revisão e registro da validação humana, se essa funcionalidade for implementada.

## Avaliação

- Verificar visualmente e corrigir as caixas do rastreador antes de usá-las como rótulos de treinamento.
- Separar treino, validação e teste por vídeo/procedimento antes de treinar; frames do mesmo vídeo não podem cruzar essas partições.
- Avaliar o detector em vídeos não usados no treinamento e relatar erros, inclusive oclusão, desfoque e enquadramento incompleto.
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

Demonstrar um pipeline reprodutível que identifica fases/instrumentos conforme os rótulos disponíveis, produz alertas rastreáveis para revisão humana e avalia quantitativamente seus acertos e limitações, sem alegar validação clínica.

## Referências iniciais

- Dataset Cholec80 e informações de acesso: [CAMMA — Datasets](https://camma.unistra.fr/datasets/).
- Publicação associada ao Cholec80: A. P. Twinanda et al., *EndoNet: A Deep Architecture for Recognition Tasks on Laparoscopic Videos*, IEEE Transactions on Medical Imaging, 2017.
