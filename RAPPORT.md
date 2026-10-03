# RAPPORT

Mesures prises le 4 octobre 2026 sur ma machine (Windows 11, Docker Desktop 4.92.0, Docker Engine 29.8.0, Compose 5.5.1). Celles des questions 2, 3 et 4 viennent de `scripts/mesures.sh`.

## 1. Image de base

J'ai retenu `python:3.13.7-slim-bookworm` : image officielle, tag figé sur la version de Python et sur celle de Debian.

Je n'ai pas pris la variante complète (`python:3.13.7-bookworm`) parce qu'elle ajoute les compilateurs et les en-têtes de développement, qui servent à compiler des dépendances. Ici pip n'a rien compilé : le log du build montre 16 paquets, tous téléchargés en wheels.

Je n'ai pas pris alpine parce qu'Alpine utilise musl au lieu de glibc. Les trois paquets compilés du projet (`greenlet`, `pydantic_core`, `sqlalchemy`) ont été téléchargés en wheels `manylinux`, faits pour glibc. Sur Alpine, pip dépend de l'existence de wheels `musllinux` pour chaque paquet, sinon il compile depuis les sources. De plus `useradd`, que mon Dockerfile utilise, n'existe pas dans Alpine de base. Je n'ai pas testé cette variante.

## 2. Cache

Mes instructions vont de la plus stable à la plus volatile :

```dockerfile
FROM python:3.13.7-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 ...
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app/ ./app/
USER appuser
EXPOSE 8000
HEALTHCHECK ...
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Une couche est réutilisée si son instruction et ses fichiers d'entrée n'ont pas changé, et si toutes les couches précédentes ont été réutilisées. Quand je modifie une ligne de code, seule `COPY app/ ./app/` est refaite : `requirements.txt` n'a pas changé, donc `pip install` reste en cache. Les quatre instructions qui suivent ne coûtent rien, ce sont des métadonnées (0B dans `docker history`).

Premier build, sans cache (`docker compose build --no-cache --progress=plain web`, extrait) :

```
#8 [2/6] WORKDIR /app
#8 CACHED
#9 [3/6] RUN useradd --create-home --uid 10001 appuser
#9 DONE 7.5s
#10 [4/6] COPY requirements.txt .
#10 DONE 2.5s
#11 [5/6] RUN pip install -r requirements.txt
#11 DONE 29.9s
#12 [6/6] COPY app/ ./app/
#12 DONE 1.6s

real    1m22.427s
```

Second build, après l'ajout d'une ligne dans `app/main.py` (extrait) :

```
#7 [2/6] WORKDIR /app
#7 CACHED
#8 [3/6] RUN useradd --create-home --uid 10001 appuser
#8 CACHED
#9 [4/6] COPY requirements.txt .
#9 CACHED
#10 [5/6] RUN pip install -r requirements.txt
#10 CACHED
#11 [6/6] COPY app/ ./app/
#11 DONE 2.7s

real    0m16.965s
```

Le build passe de 1 min 22 s à 17 s. Si `COPY app/` était placé avant `pip install`, chaque modification du code relancerait les 30 s d'installation. Même avec `--no-cache`, BuildKit a affiché `WORKDIR` en `CACHED` ; toutes les autres étapes ont été réexécutées.

## 3. Taille

```
IMAGE             ID             DISK USAGE   CONTENT SIZE
todoist-web:1.0   3daf7d512bc0        238MB         56.8MB
```

`docker history todoist-web:1.0` donne le détail des couches :

- image de base : 136,5 Mo (Debian bookworm 85,2 Mo, paquets système 10,4 Mo, Python 40,9 Mo)
- `RUN pip install` : 44,5 Mo
- `COPY app/` : 77,8 ko
- `useradd`, `requirements.txt`, `WORKDIR` : moins de 100 ko

Les couches font 181 Mo une fois décompressées. `CONTENT SIZE` (56,8 Mo) est la taille compressée, celle qui transite lors d'un `push` ou d'un `pull`. `DISK USAGE` (238 Mo) est la somme des deux.

Je n'ai pas de mesure avant et après : l'image a été construite d'emblée sur `slim`, avec `PIP_NO_CACHE_DIR=1` pour ne pas garder le cache de pip dans la couche, et un `.dockerignore` qui écarte les tests, les scripts et `.env`.

## 4. Persistance

MySQL écrit ses données dans `/var/lib/mysql`, où `compose.yaml` monte le volume nommé `db_data` (nom réel : `todoist_db_data`). Les données sont donc dans le volume, pas dans le conteneur.

`docker compose down` arrête et supprime les trois conteneurs et le réseau `todoist_default`, mais pas le volume. Au `up` suivant, Compose recrée le réseau et les conteneurs et remonte le même volume. MySQL trouve un dossier de données déjà rempli : il ne réinitialise rien et ignore les variables `MYSQL_*`. `web` attend que `db` soit `healthy`, puis `create_all` ne crée aucune table puisqu'elles existent.

Mesuré : 2 tâches au départ, 3 après un ajout, 3 après `docker compose restart`, 3 après `down` puis `up`. Après le `down`, `docker volume ls` affichait toujours `todoist_db_data`.

`docker compose down -v` supprime en plus le volume. Au `up` suivant, Compose crée un volume vide, MySQL refait toute son initialisation (base et utilisateur créés à partir de `.env`), et l'application recrée ses tables et le projet « Boîte de réception ».

Mesuré sur une copie du projet lancée sous un autre nom (`-p todoist-verif`) pour ne pas effacer ma base : 1 tâche, puis `down -v` affiche `Volume todoist-verif_db_data Removed`, puis `up` rend 0 tâche. Ce `up` a pris 2 min 14 s, contre 28 s après un simple `down`.

## 5. Difficulté

Pour vérifier que le projet démarre chez quelqu'un d'autre, j'ai copié le dépôt dans un dossier vide, fait `cp .env.example .env`, puis lancé `docker compose -p todoist-verif up -d --build --wait`. Après 2 min 13 s :

```
 Container todoist-verif-db-1 Error dependency db failed to start
dependency failed to start: container todoist-verif-db-1 is unhealthy
```

`web` n'avait pas démarré et `curl` répondait `Failed to connect to localhost port 8080`. Dans mon dossier de travail, tout fonctionnait.

Diagnostic :

1. `docker compose ps` montrait `db` en `Up About a minute (unhealthy)`. Le conteneur tournait : ce n'était pas un plantage de MySQL, mais un verdict du healthcheck.
2. `docker logs --timestamps todoist-verif-db-1` : `Initializing database files` à 00:24:36, `MySQL init process done. Ready for start up.` à 00:26:57, serveur prêt sur le port 3306 à 00:27:11. L'initialisation a duré 2 min 35 s.
3. `docker inspect -f '{{.State.Health.Status}}'` toutes les 5 s : `starting` jusqu'à 118 s, `unhealthy` à 123 s, `healthy` à 161 s.
4. Mon healthcheck laissait `start_period: 20s` plus 20 essais espacés de 5 s, soit 120 s.

La cause : sur un volume vide, MySQL met plus de temps à s'initialiser que le délai accordé par mon healthcheck. `db` est déclarée `unhealthy`, et comme `web` dépend de `db` avec `condition: service_healthy`, Compose abandonne son démarrage. `db` devient `healthy` 38 s plus tard, mais trop tard : il fallait relancer `docker compose up -d`. Je ne le voyais pas chez moi parce que mon volume existait déjà et que MySQL démarre alors en moins de 30 s.

Correction : `start_period: 300s` dans `compose.yaml`. Pendant ce délai, les échecs ne sont pas comptés et le premier succès rend le service `healthy` tout de suite, donc rien n'est ralenti quand MySQL est rapide.

Vérification : le même test réussit dès la première commande. Les trois services sont `healthy` après 6 min 38 s, construction de l'image comprise, `GET /` répond 200 et `db` ne publie aucun port.

Ce que j'en retiens : tester sur un volume vide, pas seulement sur ma machine où tout est déjà initialisé.
