#!/usr/bin/env python3
"""Mostra a letra da música do Spotify palavra por palavra, em letras gigantes.

Funciona junto com o sptlrx:
    sptlrx pipe | python letra_grande.py
Opções:
    --vermelho   letras vermelho-sangue em vez de brancas
    --linha      mostra a linha inteira de uma vez, em vez de palavra por palavra
"""
import os, queue, shutil, sys, threading, unicodedata

FONTE = {
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#### ", "    #", "    #", " ### ", "    #", "    #", "#### "],
    "4": ["#   #", "#   #", "#   #", "#####", "    #", "    #", "    #"],
    "5": ["#####", "#    ", "#    ", "#### ", "    #", "    #", "#### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "!": ["#", "#", "#", "#", "#", " ", "#"],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    ".": [" ", " ", " ", " ", " ", " ", "#"],
    ",": ["  ", "  ", "  ", "  ", "  ", " #", "# "],
    "'": ["#", "#", " ", " ", " ", " ", " "],
    "-": ["    ", "    ", "    ", "####", "    ", "    ", "    "],
    " ": ["   "] * 7,
}

ESPERAR = object()   # ainda não chegou a próxima linha

def limpar(texto):
    # tira acentos (Ç vira C, Ã vira A) e ignora o que a fonte não tem
    texto = unicodedata.normalize("NFD", texto.upper())
    return "".join(c for c in texto if c in FONTE)

def montar(texto, largura_px):
    linhas = [""] * 7
    for c in texto:
        for i, parte in enumerate(FONTE[c]):
            linhas[i] += parte + " "
    return [l.rstrip().replace("#", "█" * largura_px).replace(" ", " " * largura_px) for l in linhas]

def mostrar(texto, cor):
    cols, linhas_term = shutil.get_terminal_size()
    texto = limpar(texto)
    desenho = montar(texto, 2)
    if desenho and max(map(len, desenho)) > cols:
        desenho = montar(texto, 1)       # palavra comprida: letras mais estreitas
    largura = max(map(len, desenho)) if texto else 0
    topo = max(0, (linhas_term - 7) // 2)
    esquerda = " " * max(0, (cols - largura) // 2)
    saida = "\x1b[2J\x1b[H" + "\n" * topo
    if texto:
        saida += cor + "\n".join(esquerda + l for l in desenho) + "\x1b[0m"
    sys.stdout.write(saida)
    sys.stdout.flush()

def ler_linhas(fila):
    for linha in sys.stdin:
        fila.put(linha.strip())
    fila.put(None)

def main():
    if os.name == "nt":
        os.system("")                   # liga as cores ANSI no Windows
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass
    cor = "\x1b[38;2;255;42;69m" if "--vermelho" in sys.argv else "\x1b[1;97m"
    palavra_por_palavra = "--linha" not in sys.argv
    fila = queue.Queue()
    threading.Thread(target=ler_linhas, args=(fila,), daemon=True).start()
    sys.stdout.write("\x1b[?25l")
    try:
        linha = fila.get()
        while linha is not None:
            proxima = ESPERAR
            if palavra_por_palavra and linha:
                for palavra in linha.split():
                    mostrar(palavra, cor)
                    try:
                        # palavras longas ficam um pouco mais na tela
                        proxima = fila.get(timeout=0.18 + 0.045 * len(palavra))
                        break
                    except queue.Empty:
                        continue
            else:
                mostrar(linha, cor)
            linha = fila.get() if proxima is ESPERAR else proxima
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[2J\x1b[H")

if __name__ == "__main__":
    main()
