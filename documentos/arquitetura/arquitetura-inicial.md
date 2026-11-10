# Arquitetura inicial do protótipo de análise de vídeo

## Status

Proposta inicial para orientar a primeira implementação do protótipo acadêmico. A arquitetura deve permanecer simples e pode evoluir conforme os casos de uso e as regras de análise forem definidos.

## Objetivo

Construir uma ferramenta local, acionada por CLI, que processe vídeos cirúrgicos e futuramente destaque possíveis ocorrências fora do padrão para revisão humana. Na primeira etapa, o foco é estruturar a aplicação e ler vídeos; detecção de objetos, definição de anomalias e geração de alertas ficam para etapas posteriores.

O protótipo não confirma anomalias clínicas, não diagnostica e não deve orientar decisões durante cirurgias reais.

## Princípios

- Organização inspirada em Clean Architecture, sem criar camadas ou abstrações sem necessidade concreta.
- Separação entre entrada (CLI), casos de uso e detalhes de infraestrutura.
- Orientação a objetos e tipagem explícita quando contribuírem para clareza e testabilidade.
- Código Python seguindo convenções idiomáticas: `snake_case` para funções e variáveis, type hints e estruturas simples (`dataclass` ou `Protocol`) quando úteis.
- Dependências de bibliotecas de vídeo e visão computacional encapsuladas na infraestrutura.
- Testes automatizados para os casos de uso e para componentes que possam ser testados sem vídeos reais.

## Estrutura proposta

```text
src/
  video_review/
    __init__.py
    cli.py
    application/
      __init__.py
      analyze_video.py
    infrastructure/
      __init__.py
      video_reader.py
    models.py                 # criar apenas se houver tipos compartilhados úteis
tests/
```

Esta estrutura é uma referência inicial, não uma exigência de criar todos os arquivos antecipadamente. O pacote pode ser renomeado se o projeto adotar outro nome.

## Responsabilidades

### CLI (`cli.py`)

- Receber os argumentos do usuário, como caminho do vídeo e opções de execução.
- Validar entradas simples e apresentar mensagens de erro compreensíveis.
- Chamar o caso de uso apropriado.
- Exibir ou salvar o resultado sem conter regras de análise de vídeo.

### Aplicação (`application/analyze_video.py`)

- Implementar o caso de uso de análise de vídeo.
- Coordenar a leitura do vídeo e, futuramente, as etapas de inferência e criação de relatório.
- Não depender diretamente de OpenCV, codecs ou outros detalhes específicos do leitor.

### Infraestrutura (`infrastructure/video_reader.py`)

- Abrir o vídeo e obter metadados básicos, como dimensões, taxa de quadros, duração quando disponível e quantidade de frames.
- Ler ou extrair frames por meio da biblioteca escolhida.
- Converter erros da biblioteca para falhas que a aplicação consiga tratar de maneira consistente.
- Manter detalhes da biblioteca de vídeo isolados deste módulo.

### Domínio

Não será criado um módulo de domínio dedicado na primeira versão. Regras simples podem permanecer no caso de uso. Se surgirem políticas mais complexas — por exemplo, quais instrumentos são esperados por fase ou como classificar sinais para revisão — elas poderão ser extraídas para um domínio independente.

## Fluxo inicial

```text
Usuário → CLI → caso de uso AnalyzeVideo → VideoReader → metadados/frames → resultado → CLI
```

Na primeira entrega, o fluxo pode limitar-se a abrir um vídeo, validar que ele é legível, obter metadados e percorrer alguns ou todos os frames. Ainda não deve classificar movimentos como corretos, incorretos ou anômalos.

## Resultado inicial

O resultado deve conter, no mínimo, informação suficiente para confirmar o processamento, como caminho ou nome do arquivo, dimensões do vídeo e quantidade de frames lidos. Duração e FPS podem ser incluídos quando o leitor os fornecer de modo confiável.

O formato de saída (texto, JSON ou outro) e um modelo definitivo de resultado ainda serão decididos ao implementar a CLI. Não incluir diagnóstico ou afirmações clínicas.

## Testabilidade

- O caso de uso deve poder ser testado com um leitor de vídeo substituto/falso, sem depender de codecs ou arquivos grandes.
- A leitura real pode ser testada separadamente com um vídeo pequeno de teste, se houver um fixture adequado e permitido.
- Testar caminhos inexistentes, arquivos inválidos e vídeos sem frames legíveis.
- Evitar armazenar vídeos clínicos ou dados pessoais no repositório sem autorização e justificativa.

## Decisões em aberto

- Nome e interface final da CLI.
- Biblioteca de leitura de vídeo e formatos suportados.
- Uso do Cholec80 e detalhes da licença, distribuição e preparação dos dados.
- Modelo de visão computacional (modelo pré-treinado, ajuste fino ou regras sobre detecções existentes).
- Classes e anotações disponíveis para detecção/localização de instrumentos.
- Definição experimental de “possível ocorrência fora do padrão” por fase.
- Formato e destino de relatórios; critérios de revisão humana.
- Necessidade de um backend Java ou de um serviço separado. A primeira versão permanece local e em Python, salvo decisão posterior.

## Próxima etapa sugerida

Implementar a CLI mínima para receber um caminho de vídeo e retornar metadados de leitura, usando o caso de uso e o leitor de infraestrutura separados. Validar esse fluxo com testes antes de adicionar modelos de visão ou regras de alerta.
