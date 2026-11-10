# Avaliação de acionamento das skills

Os arquivos `wiki-referencia.json` e `requisitos.json` contêm consultas positivas (`should_trigger: true`) e negativas (`false`). Os casos negativos são próximos do escopo, incluindo pedidos que devem encaminhar para a outra skill.

## Execução manual no OpenCode

1. Inicie sessões novas na raiz do projeto. Não mencione `@wiki-referencia` ou `@requisitos` nos prompts, pois isso força o carregamento e invalida o teste de descoberta automática.
2. Envie cada consulta como prompt independente e observe a transcrição/evento de ferramentas da sessão.
3. Registre `pass` quando a skill esperada for carregada em um caso positivo, ou quando não for carregada em um caso negativo. Para casos negativos sobre a outra base local, carregamento da skill da outra base é aceitável; carregamento da skill testada não é.
4. Repita cada consulta três vezes em sessões novas para reduzir o efeito de variação do modelo.
5. Calcule separadamente, para cada skill, a taxa de acerto dos positivos (recall) e dos negativos (especificidade). Analise falsos negativos e falsos positivos antes de alterar `description`.

## Execução automatizada opcional

O OpenCode oferece `opencode run --format json`, mas essa avaliação consulta o modelo configurado e pode consumir créditos. Execute manualmente os casos e inspecione a chamada da ferramenta `skill` no fluxo JSON da execução. Este repositório não dispara chamadas ao modelo durante os testes unitários.

Esses casos são uma baseline inicial, não um benchmark universal. Ao revisá-los, preserve exemplos positivos e negativos e mantenha alguns prompts novos separados para validação, evitando ajustar as descrições somente às frases conhecidas.
