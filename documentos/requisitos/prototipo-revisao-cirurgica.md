# Protótipo acadêmico de apoio à revisão cirúrgica

## Visão geral

Proposta de um protótipo acadêmico que analisa vídeos de colecistectomia laparoscópica do dataset Cholec80 para sinalizar **possíveis ocorrências fora do padrão** e facilitar a revisão posterior por uma pessoa. O sistema não confirma anomalias clínicas, não diagnostica e não deve orientar procedimentos cirúrgicos reais.

## Objetivo

Explorar se informações de fase cirúrgica e presença de instrumentos podem ser usadas para destacar frames ou intervalos que mereçam revisão humana — por exemplo, quando uma ferramenta esperada para uma fase não é detectada ou quando a confiança do modelo é baixa.

## Base de dados

O Cholec80 contém vídeos de colecistectomias laparoscópicas, rótulos de fases cirúrgicas e anotações de presença de instrumentos. Antes da implementação, a equipe deve verificar o formato, a cobertura e a granularidade das anotações disponíveis para a versão escolhida.

As anotações de presença não equivalem necessariamente a localizações de objetos. Um detector que produza caixas delimitadoras (*bounding boxes*) requer anotações espaciais apropriadas; não se deve presumir que estejam disponíveis para todas as ferramentas e frames.

## Fluxo proposto

1. Obter os dados e revisar a licença, as condições de uso e os requisitos de citação do Cholec80.
2. Carregar vídeos ou frames e as anotações correspondentes de fase e presença de instrumentos.
3. Usar um modelo pré-treinado ou uma abordagem de classificação adequada às anotações. Treinamento ou ajuste fino é opcional e depende da tarefa, das classes e dos rótulos disponíveis.
4. Estimar a fase cirúrgica e quais instrumentos estão presentes em cada frame ou intervalo.
5. Definir, de forma explícita e justificável, quais instrumentos são esperados em cada fase. Essa regra deve ser tratada como hipótese experimental, não como protocolo clínico.
6. Sinalizar para revisão humana situações como instrumento esperado não detectado, classe inesperada ou baixa confiança do modelo.
7. Agrupar sinais próximos em possíveis ocorrências e gerar relatório com vídeo, timestamp, fase estimada, detecções, confiança e motivo do alerta.
8. Permitir que a pessoa revisora marque o alerta como relevante, falso positivo ou inconclusivo.

## Saídas esperadas

- Lista de possíveis ocorrências com timestamps para navegação no vídeo.
- Evidências do modelo por ocorrência: fase, classes detectadas e respectivas confianças.
- Relatório resumido de alertas e resultados da revisão humana.
- Métricas experimentais, como precisão, recall, taxa de falsos alertas e desempenho por fase, quando as anotações permitirem calculá-las.

## Avaliação

- Separar vídeos de treino, validação e teste por procedimento, evitando que frames do mesmo vídeo apareçam em mais de uma partição.
- Comparar os alertas com as anotações disponíveis e, se houver critérios adicionais, com revisão humana documentada.
- Relatar falsos positivos e falsos negativos, inclusive casos de oclusão, desfoque, enquadramento incompleto e baixa confiança.
- Não interpretar a pontuação do modelo como probabilidade clínica sem calibração e validação apropriadas.

## Limitações e segurança

- Uma ferramenta não detectada pode estar presente, mas ocultada, fora do enquadramento ou não reconhecida pelo modelo.
- Uma classe não prevista no dataset não deve ser automaticamente tratada como anomalia.
- A ausência de uma anotação não prova a ausência do objeto no vídeo.
- Rótulos de presença de instrumentos podem não oferecer localização espacial; a detecção por caixas depende de *bounding boxes* anotadas.
- Os resultados dependem da qualidade, cobertura e licença dos dados, bem como da distribuição dos vídeos e das condições de captura.
- O protótipo é exclusivamente acadêmico e de apoio à revisão. Não deve ser usado para diagnóstico, avaliação clínica definitiva ou decisão intraoperatória.

## Critério de sucesso acadêmico

Demonstrar um pipeline reprodutível que identifica fases/instrumentos conforme os rótulos disponíveis, produz alertas rastreáveis para revisão humana e avalia quantitativamente seus acertos e limitações, sem alegar validação clínica.

## Referências iniciais

- Dataset Cholec80 e informações de acesso: [CAMMA — Datasets](https://camma.unistra.fr/datasets/).
- Publicação associada ao Cholec80: A. P. Twinanda et al., *EndoNet: A Deep Architecture for Recognition Tasks on Laparoscopic Videos*, IEEE Transactions on Medical Imaging, 2017.
