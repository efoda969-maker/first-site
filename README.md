# ALL STAR BURGERS

Site da hamburgueria **ALL STAR BURGERS**: uma apresentação animada controlada pela rolagem, seguida do cardápio com sacola de pedidos.

Abra `index.html` por um servidor local (as imagens da sequência são carregadas via `fetch`):

```bash
npx http-server -p 8080 .
# ou
python3 -m http.server 8080
```

## Como funciona

- **Cena fixa + rolagem**: a seção `#experiencia` é alta (≈7 telas) e o palco (`.stage`) fica `sticky`. O progresso da rolagem (0 → 1) escolhe o quadro da sequência e desenha num `<canvas>`. Ao rolar para cima, tudo volta em sentido inverso.
- **Movimento suave**: o progresso é amortecido a cada quadro e dois quadros vizinhos são misturados, então a animação não “pula” mesmo com 180 imagens.
- **Pré-carregamento**: os quadros são baixados antes de liberar a página (do mais espaçado para o mais denso: 1 a cada 16, 8, 4, 2, 1) e decodificados com `img.decode()`, evitando travamentos na rolagem.
- **Textos sincronizados**: cada bloco `.step` tem `data-in` / `data-out` (em progresso 0–1). As etiquetas dos ingredientes acompanham as camadas usando as posições projetadas exportadas pelo Blender (`assets/seq/meta.json`).
- **Celular**: há duas sequências, `desktop` (16:9) e `mobile` (9:16), recortadas do mesmo render quadrado. No retrato, os textos ficam acima e abaixo do produto.
- **Sacola**: os botões “Pedir” adicionam itens; “Finalizar pelo WhatsApp” monta a mensagem do pedido. Defina o número da loja em `WHATSAPP_NUMBER`, no topo de `assets/js/main.js`.

## Etapas da sequência

| Progresso | Etapa |
|---|---|
| 0.00 – 0.14 | Cheeseburger sobre papel branco, mesa escura, luz de estúdio |
| 0.14 – 0.43 | O hambúrguer cresce, as camadas se separam e o fundo vai do escuro ao creme |
| 0.43 – 0.62 | As camadas se juntam; batata, milkshake e molhos chegam ao redor |
| 0.62 – 0.95 | A caixa preta da marca entra, os produtos pulam para dentro e a tampa fecha |
| 0.95 – 1.00 | Caixa fechada; em seguida o cardápio |

## Imagens (renderizações 3D)

Tudo foi modelado e renderizado proceduralmente no Blender (Cycles). Os scripts ficam em `render-src/`:

| Arquivo | Função |
|---|---|
| `lib.py` | utilitários de geometria, curvas de animação e nós de material |
| `burger.py` | pão, alface, tomate, carne, cheddar, molho, bacon, frango, picles |
| `props.py` | batata na embalagem, milkshake, potes de molho e a caixa com tampa articulada |
| `env.py` | mesa de madeira escura → fundo creme, papel, luzes e câmera |
| `sequence.py` | coreografia completa e renderização dos quadros |
| `menu.py` | fotos do cardápio |
| `make_logo.py` | logotipo (SVG com as letras convertidas em curvas) e artes da embalagem |
| `build_assets.py` | recortes 16:9 / 9:16, WebP, cores de borda e `meta.json` |

```bash
# Blender 4.5 LTS; as artes da embalagem são PNGs gerados a partir de make_logo.py
python render-src/make_logo.py fonts/ assets/img/ build/tex/
ASB_TEX=build/tex blender -b -P render-src/sequence.py -- --out build/seq --frames 180 --size 1280 --samples 8
ASB_TEX=build/tex blender -b -P render-src/menu.py -- --item classic --out build/menu
python render-src/build_assets.py build/seq build/menu .
```

Fontes: Anton, Barlow Condensed e Barlow (Google Fonts, licença OFL).
