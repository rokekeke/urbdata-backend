# Painel informativo de feição

Documento funcional compartilhado entre as equipes de frontend e backend.

## Finalidade

Exibir informações contextuais de uma geometria selecionada sem interromper a leitura do mapa. A configuração visual é definida por camada e editada por um dropdown compacto no painel de ferramentas.

Esta documentação descreve o comportamento esperado. O recurso ainda não está implementado no protótipo.

## Fluxo principal

1. O usuário ativa a ferramenta de inspeção ou mantém o modo padrão de seleção.
2. Ao clicar em uma geometria selecionável, o mapa fornece `feature.id` e `properties`.
3. O frontend grava a seleção como estado temporário.
4. O painel abre na viewport e resolve os blocos configurados para a camada.
5. Atributos são lidos das propriedades da feição; indicadores são associados pelo UUID.
6. Um novo clique substitui a feição ativa. Fechar o painel limpa a seleção.

## Estrutura da interface

### Painel na viewport

Ordem sugerida:

- cabeçalho com título da feição, nome da camada e ação de fechar;
- blocos de texto para informações de destaque;
- tabela de atributos e indicadores;
- mensagens locais para valor ausente ou indicador indisponível;
- ação opcional de fixar, condicionada à validação de produto.

O painel não deve bloquear controles essenciais do mapa. Em telas estreitas, deve migrar para uma gaveta inferior; em desktop, deve usar largura compacta ou média.

### Dropdown de diagramação

O menu é aberto por uma ação **Configurar painel da feição** no painel de ferramentas. Deve conter:

- interruptor `Exibir ao selecionar uma feição`;
- seletor do campo de título;
- lista ordenável de blocos;
- inclusão de bloco `Texto` ou `Tabela`;
- seletor de campos com busca e indicação da origem `Atributo` ou `Indicador`;
- edição de rótulo, visibilidade, casas decimais, prefixo, sufixo e estilo de texto;
- largura do painel e pré-visualização imediata;
- ações `Restaurar` e `Aplicar`.

O dropdown altera um rascunho local. `Aplicar` atualiza a visualização do documento; a persistência dependerá do CRUD de `MapDocument`.

## Estados de interface

| Estado | Comportamento |
| --- | --- |
| Sem seleção | Painel fechado; permanece apenas a ferramenta de configuração. |
| Carregando | Exibe estrutura reduzida e mantém a identificação da feição. |
| Selecionada | Renderiza os blocos configurados na ordem salva. |
| Campo ausente | Mostra `Sem dado`, sem converter para zero. |
| Indicador não executado | Mostra `Indicador ainda não calculado` e, quando aplicável, acesso ao Diagnóstico. |
| Não aplicável | Mostra o estado explicitamente. |
| Erro | Preserva a seleção e oferece nova tentativa. |
| Camada não selecionável | Não abre o painel e não produz falso estado de seleção. |

## Modelo de estado frontend

```ts
type SelectedFeature = {
  layerId: string;
  featureId: string;
  properties: Record<string, unknown>;
};

type FeaturePanelConfig = {
  enabled: boolean;
  titleField: string | null;
  width: "compact" | "medium";
  blocks: Array<TextBlock | TableBlock>;
};
```

O estado de `SelectedFeature` é efêmero. `FeaturePanelConfig` deve ser mantido no rascunho do documento cartográfico e, após evolução do backend, persistido por camada.

## Fontes de dados

- **Atributos:** `properties` recebidas no GeoJSON da camada.
- **Metadados de campos:** endpoint de atributos, incluindo nome, tipo detectado e amostras.
- **Indicadores por feição:** resultados associados por `feature.id`/UUID.
- **Configuração persistente futura:** `DocumentLayer.interaction.feature_panel` no `MapDocument`.

O frontend não deve inferir silenciosamente formatações incompatíveis com o tipo detectado. Formatos inválidos precisam ser desabilitados no editor.

## Regras de diagramação

- usar apenas estilos e formatos enumerados;
- não aceitar HTML, CSS, Markdown executável ou scripts fornecidos pelo usuário;
- limitar quantidade de blocos, campos e tamanho de texto;
- manter ordem determinística dos campos;
- preservar zero, vazio e não aplicável como valores distintos;
- usar rótulo amigável sem perder a chave original do campo;
- indicar visualmente a origem de indicadores e atributos;
- fornecer fallback para configuração antiga baseada somente em `tooltip_fields`.

## Integração e contrato

O contrato v1 atual aceita apenas `selectable`, `tooltip_fields` e `filters` em `interaction`. Como propriedades desconhecidas são rejeitadas, `feature_panel` exige atualização formal da ADR 014 e dos modelos Pydantic.

Até essa atualização, o frontend pode implementar a experiência com configuração temporária e converter `tooltip_fields` em uma tabela simples de leitura. Não deve enviar `feature_panel` ao backend atual.

## Fora do primeiro recorte

- editor livre de HTML ou CSS;
- gráficos complexos dentro do painel;
- múltiplas feições abertas simultaneamente;
- comparação entre versões;
- exportação do painel junto da composição cartográfica;
- compartilhamento de presets entre projetos.

## Critérios de aceite do primeiro protótipo

- clicar em uma feição abre o painel correto;
- clicar em outra feição substitui o conteúdo sem acumular seleções;
- o dropdown permite escolher e ordenar campos demonstrativos;
- mudanças de título, tabela e texto aparecem na prévia;
- fechar o painel limpa o destaque no mapa;
- navegação por teclado, foco visível e fechamento por `Esc` funcionam;
- nenhum dado demonstrativo é confundido com resposta real do backend;
- a interface informa que as configurações ainda não são persistidas.

