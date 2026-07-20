# URBDATA UX

Protótipo funcional e isolado da experiência do URBDATA, construído a partir das decisões registradas nas notas 27, 28 e 29 do vault do projeto.

## Escopo desta primeira versão

- shell responsivo da plataforma;
- navegação entre as áreas principais;
- aba Documentação como editor cartográfico;
- múltiplas camadas MapLibre;
- visibilidade e ordem das camadas;
- representação única, categórica e sequencial;
- paletas, transparência, cor e estilo de linha;
- opção sem mapa-base e OSM claro;
- legenda vinculada à configuração;
- salvamento local demonstrativo;
- exportação PNG local usando o canvas do próprio MapLibre;
- dados explícitos de demonstração, sem chamadas ao backend.

## Limites intencionais

- nenhum contrato de API foi inventado antes da publicação da ADR 014;
- nenhuma configuração é persistida no backend;
- o join indicador-feição está demonstrado nos dados locais, mas será integrado aos resultados reais após o OpenAPI definitivo;
- PDF, SVG, autenticação, tiles e deck.gl estão fora do MVP atual.

## Desenvolvimento

```bash
pnpm dev
pnpm build
```

