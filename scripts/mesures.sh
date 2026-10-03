#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Relève les mesures demandées dans le RAPPORT, sur VOTRE machine.
#   bash scripts/mesures.sh              -> build, cache, taille, restart, down/up
#   bash scripts/mesures.sh --avec-down-v -> ajoute le test "down -v" (EFFACE LA BASE)
# Résultats écrits dans mesures/*.txt (dossier ignoré par l'image Docker).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=mesures
mkdir -p "$OUT"
URL="http://localhost:${APP_PORT:-8080}/api/health"

[ -f .env ] || { echo "Fichier .env absent : faites d'abord  cp .env.example .env"; exit 1; }

attendre_api() {
  for _ in $(seq 1 60); do
    if r=$(curl -fsS "$URL" 2>/dev/null); then echo "$r"; return 0; fi
    sleep 1
  done
  echo "API injoignable après 60 s"; return 1
}

echo "== 1. Build à froid (sans cache)"
{ time docker compose build --no-cache --progress=plain web ; } > "$OUT/build1.txt" 2>&1
tail -n 4 "$OUT/build1.txt"

echo "== 2. Modification d'une ligne de code puis rebuild"
cp app/main.py /tmp/main.py.bak
trap 'cp /tmp/main.py.bak app/main.py' EXIT
echo "# modification de test $(date +%s)" >> app/main.py   # contenu unique -> invalide le cache
{ time docker compose build --progress=plain web ; } > "$OUT/build2.txt" 2>&1
cp /tmp/main.py.bak app/main.py
grep -E "CACHED|DONE|real" "$OUT/build2.txt" | tail -n 12

echo "== 3. Taille de l'image"
docker image ls todoist-web:1.0 | tee "$OUT/taille.txt"
docker history todoist-web:1.0 >> "$OUT/taille.txt"

echo "== 4. Persistance"
{
  docker compose up -d
  echo "--- état initial"; attendre_api
  curl -fsS -X POST "http://localhost:${APP_PORT:-8080}/api/tasks/quick" \
       -H 'Content-Type: application/json' -d '{"text":"Test persistance demain p1 #Mesures"}'
  echo; echo "--- après ajout"; attendre_api
  docker compose restart;  echo "--- après restart"; attendre_api
  docker compose down;     docker volume ls | grep db_data || true
  docker compose up -d;    echo "--- après down + up"; attendre_api
  if [ "${1:-}" = "--avec-down-v" ]; then
    docker compose down -v; docker volume ls | grep db_data || echo "(volume supprimé)"
    docker compose up -d;   echo "--- après down -v + up"; attendre_api
  fi
} 2>&1 | tee "$OUT/persistance.txt"

echo "Mesures enregistrées dans $OUT/"
