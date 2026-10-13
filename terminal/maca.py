#!/usr/bin/env python3
"""Maçã vermelho-sangue girando no terminal (animação 2D).

Uso:  python maca.py            (Ctrl+C para sair)
      python maca.py --lenta    (gira mais devagar, bom para gravar)
"""
import math, os, shutil, sys, time

LARGURA = 44          # colunas; cada linha do terminal vale 2 pixels na vertical
ALTURA_PX = 44
LUZ = (-0.5, 0.6, 0.62)

def dentro_da_maca(u, v):
    # dois lobos em cima, um corpo arredondado embaixo e a covinha do cabo
    corpo = (u - 0.27) ** 2 + (v - 0.08) ** 2 < 0.62 ** 2 or \
            (u + 0.27) ** 2 + (v - 0.08) ** 2 < 0.62 ** 2 or \
            u ** 2 + (v + 0.2) ** 2 < 0.66 ** 2
    covinha = u ** 2 + (v - 0.78) ** 2 < 0.2 ** 2
    return corpo and not covinha and v > -0.86

def pixel(x, y, giro):
    """Cor RGB do pixel (x, y) com a maçã girada pelo ângulo `giro`, ou None."""
    u = ((x + 0.5) / LARGURA * 2 - 1) * 1.2
    v = (1 - (y + 0.5) / ALTURA_PX * 2) * 1.2 + 0.12
    c = math.cos(giro)
    # cabo: não gira, só balança um pouco
    if abs(u - 0.04 * c) < 0.045 and 0.6 < v < 1.08:
        return (92, 48, 28)
    # folha: gira junto, troca de lado quando a maçã vira
    fx, fy = 0.08 * c, 0.98
    lu, lv = (u - fx) / max(abs(c), 0.15), v - fy
    if (lu * 0.8 + lv * 0.6) ** 2 / 0.075 + (-lu * 0.6 + lv * 0.8) ** 2 / 0.012 < 1 and lu > 0:
        return (40, 120, 45) if c > 0 else (25, 85, 32)
    if abs(c) < 0.06:
        return None
    um = u / c                       # desfaz o achatamento do giro
    if not dentro_da_maca(um, v):
        return None
    nu, nv = u / 0.95, (v + 0.05) / 0.95
    nz = math.sqrt(max(0.0, 1 - min(1.0, nu * nu + nv * nv)))
    n = (nu, nv, nz)
    difusa = max(0.0, sum(a * b for a, b in zip(n, LUZ)))
    brilho = max(0.0, difusa - 0.82) * 5.5
    # listrinhas sutis da casca, que mostram o giro
    listra = 0.08 * math.sin(um * 9) if c > 0 else 0.08 * math.sin(-um * 9 + 1.3)
    k = 0.28 + 0.75 * difusa + listra
    r = min(255, int(178 * k + 255 * brilho))
    g = min(255, int(10 * k + 210 * brilho))
    b = min(255, int(26 * k + 215 * brilho))
    return (r, g, b)

def quadro(giro):
    return [[pixel(x, y, giro) for x in range(LARGURA)] for y in range(ALTURA_PX)]

def desenhar(px, cols, linhas):
    margem_x = max(0, (cols - LARGURA) // 2)
    margem_y = max(0, (linhas - ALTURA_PX // 2) // 2)
    saida = ["\x1b[H", "\n" * margem_y]
    for y in range(0, ALTURA_PX, 2):
        linha = [" " * margem_x]
        for x in range(LARGURA):
            cima, baixo = px[y][x], px[y + 1][x]
            if cima and baixo:
                linha.append("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀\x1b[0m" % (*cima, *baixo))
            elif cima:
                linha.append("\x1b[38;2;%d;%d;%dm▀\x1b[0m" % cima)
            elif baixo:
                linha.append("\x1b[38;2;%d;%d;%dm▄\x1b[0m" % baixo)
            else:
                linha.append(" ")
        saida.append("".join(linha) + "\x1b[K\n")
    sys.stdout.write("".join(saida))
    sys.stdout.flush()

def main():
    if os.name == "nt":
        os.system("")                # liga as cores ANSI no terminal do Windows
    velocidade = 1.2 if "--lenta" in sys.argv else 2.4
    sys.stdout.write("\x1b[?25l\x1b[2J")
    inicio = time.time()
    try:
        while True:
            cols, linhas = shutil.get_terminal_size()
            desenhar(quadro((time.time() - inicio) * velocidade), cols, linhas)
            time.sleep(1 / 30)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")

if __name__ == "__main__":
    main()
