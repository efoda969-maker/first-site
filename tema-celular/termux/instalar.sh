#!/data/data/com.termux/files/usr/bin/bash
# Tema Blood Glass para o Termux: cores vermelho-sangue, cruz templária na abertura e prompt novo.
# Para desfazer: rode este script com o argumento "remover".

if [ "$1" = "remover" ]; then
  sed -i '/# >>> blood-glass >>>/,/# <<< blood-glass <<</d' ~/.bashrc
  for f in colors.properties termux.properties; do
    [ -f ~/.termux/$f.bak ] && mv ~/.termux/$f.bak ~/.termux/$f || rm -f ~/.termux/$f
  done
  rm -f ~/.hushlogin
  termux-reload-settings
  echo "Tema removido. Feche e abra o Termux."
  exit 0
fi

mkdir -p ~/.termux
for f in colors.properties termux.properties; do
  [ -f ~/.termux/$f ] && [ ! -f ~/.termux/$f.bak ] && cp ~/.termux/$f ~/.termux/$f.bak
done

cat > ~/.termux/colors.properties <<'EOF'
background=#140205
foreground=#f2d7da
cursor=#e0102c
color0=#2a0a0f
color1=#c4001f
color2=#e8737f
color3=#f0a07a
color4=#a8324a
color5=#d6336c
color6=#f4b6bf
color7=#e8c9cd
color8=#5c2a31
color9=#ff2a45
color10=#ff8f9c
color11=#ffc29e
color12=#d04a64
color13=#ff5c8a
color14=#ffd6db
color15=#fff2f3
EOF

cat > ~/.termux/termux.properties <<'EOF'
extra-keys = [['ESC','/','-','HOME','UP','END','PGUP'],['TAB','CTRL','ALT','LEFT','DOWN','RIGHT','PGDN']]
terminal-cursor-style = bar
terminal-cursor-blink-rate = 600
EOF

touch ~/.bashrc ~/.hushlogin
sed -i '/# >>> blood-glass >>>/,/# <<< blood-glass <<</d' ~/.bashrc
cat >> ~/.bashrc <<'EOF'
# >>> blood-glass >>>
blood_glass_banner() {
  local r=$'\e[38;5;160m' f=$'\e[38;5;224m' m=$'\e[38;5;138m' z=$'\e[0m'
  printf '\n'
  printf '%s%s%s\n' "$r" '         █████████████' "$z"
  printf '%s%s%s\n' "$r" '          ███████████' "$z"
  printf '%s%s%s\n' "$r" '           █████████' "$z"
  printf '%s%s%s\n' "$r" '   ██       ███████       ██' "$z"
  printf '%s%s%s\n' "$r" '   ████      █████      ████' "$z"
  printf '%s%s%s\n' "$r" '   █████████████████████████' "$z"
  printf '%s%s%s\n' "$r" '   █████████████████████████' "$z"
  printf '%s%s%s\n' "$r" '   █████████████████████████' "$z"
  printf '%s%s%s\n' "$r" '   ████      █████      ████' "$z"
  printf '%s%s%s\n' "$r" '   ██       ███████       ██' "$z"
  printf '%s%s%s\n' "$r" '           █████████' "$z"
  printf '%s%s%s\n' "$r" '          ███████████' "$z"
  printf '%s%s%s\n' "$r" '         █████████████' "$z"
  printf '\n%s     NON NOBIS, DOMINE%s\n' "$f" "$z"
  printf '%s     %s · %s%s\n\n' "$m" "$(date '+%d/%m/%Y %H:%M')" "$(whoami)" "$z"
}
blood_glass_banner
PS1='\[\e[38;5;160m\]✠ \[\e[38;5;224m\]\w \[\e[38;5;88m\]❯\[\e[0m\] '
# <<< blood-glass <<<
EOF

termux-reload-settings
echo "Tema Blood Glass aplicado. Feche o Termux (digite exit) e abra de novo."
