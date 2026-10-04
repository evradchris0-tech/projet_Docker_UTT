# TODOist

Application web de gestion de tâches (créer, lister, terminer, classer par projet) servie par FastAPI, avec une base MySQL et Adminer pour consulter la base.

## Prérequis

La commande est `docker compose` (Compose v2), pas l'ancien `docker-compose`.

- Docker Engine 24.0 ou plus récent
- Docker Compose 2.23 ou plus récent

## Démarrage

Le premier démarrage peut prendre plusieurs minutes, le temps que MySQL initialise la base.

```bash
git clone https://github.com/evradchris0-tech/projet_Docker_UTT.git
cd projet_Docker_UTT
cp .env.example .env
docker compose up -d --build
```

## Accès

L'application est prête quand `docker compose ps` affiche `web` en `healthy`.

- Application : http://localhost:8080
- Documentation de l'API : http://localhost:8080/docs
- Adminer : http://localhost:8081 (serveur `db`, identifiants du fichier `.env`)

## Variables d'environnement

Elles sont lues dans le fichier `.env`, créé à partir de `.env.example`.

- `MYSQL_ROOT_PASSWORD` : mot de passe du compte `root` de MySQL
- `MYSQL_DATABASE` : nom de la base créée au premier démarrage
- `MYSQL_USER` : compte MySQL utilisé par l'application
- `MYSQL_PASSWORD` : mot de passe de ce compte
- `TZ` : fuseau horaire des conteneurs
- `APP_PORT` : port de l'hôte vers l'application
- `ADMINER_PORT` : port de l'hôte vers Adminer

## Développement

Pour que les modifications du code soient prises en compte sans reconstruire l'image :

```bash
docker compose up --watch
```

Un fichier modifié dans `app/` est copié dans le conteneur, puis `web` redémarre. Une modification de `requirements.txt` reconstruit l'image.

## Commandes utiles

Dans l'ordre : voir les logs, ouvrir un shell, tout arrêter, tout arrêter en effaçant la base.

```bash
docker compose logs -f web
docker compose exec web bash
docker compose down
docker compose down -v
```
