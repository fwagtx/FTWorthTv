#!/usr/bin/env bash
# Download OFL typefaces (with their licence files) from the google/fonts repository.
# usage: bash scripts/fetch_fonts.sh out/fonts
set -uo pipefail
OUT="${1:-out/fonts}"
mkdir -p "$OUT"
BASE="https://raw.githubusercontent.com/google/fonts/main/ofl"
# family-dir  file
FILES=(
  "bodonimoda BodoniModa[opsz,wght].ttf"
  "bodonimoda BodoniModa-Italic[opsz,wght].ttf"
  "playfairdisplay PlayfairDisplay[wght].ttf"
  "playfairdisplay PlayfairDisplay-Italic[wght].ttf"
  "fraunces Fraunces[SOFT,WONK,opsz,wght].ttf"
  "fraunces Fraunces-Italic[SOFT,WONK,opsz,wght].ttf"
  "instrumentserif InstrumentSerif-Regular.ttf"
  "instrumentserif InstrumentSerif-Italic.ttf"
  "dmserifdisplay DMSerifDisplay-Regular.ttf"
  "dmserifdisplay DMSerifDisplay-Italic.ttf"
  "librecaslondisplay LibreCaslonDisplay-Regular.ttf"
  "bricolagegrotesque BricolageGrotesque[opsz,wdth,wght].ttf"
  "spacegrotesk SpaceGrotesk[wght].ttf"
  "bigshouldersdisplay BigShouldersDisplay[wght].ttf"
  "archivo Archivo[wdth,wght].ttf"
  "syne Syne[wght].ttf"
  "unbounded Unbounded[wght].ttf"
  "newsreader Newsreader[opsz,wght].ttf"
  "newsreader Newsreader-Italic[opsz,wght].ttf"
  "youngserif YoungSerif-Regular.ttf"
  "gloock Gloock-Regular.ttf"
)
for entry in "${FILES[@]}"; do
  fam="${entry%% *}"; file="${entry#* }"
  enc="${file//\[/%5B}"; enc="${enc//\]/%5D}"
  mkdir -p "$OUT/$fam"
  code=$(curl -sS -L -o "$OUT/$fam/$file" -w "%{http_code}" "$BASE/$fam/$enc" || echo "000")
  if [ "$code" != "200" ]; then rm -f "$OUT/$fam/$file"; echo "MISS $code $fam/$file"; else echo "ok   $fam/$file ($(stat -c %s "$OUT/$fam/$file") bytes)"; fi
  if [ ! -f "$OUT/$fam/OFL.txt" ]; then
    curl -sS -L -o "$OUT/$fam/OFL.txt" "$BASE/$fam/OFL.txt" || true
  fi
done
ls -R "$OUT" | head -80
