# cbio-ingest

REST API endpoints to ingest study and panel data into a cBioPortal instance.
It requires the Docker installation of cBioPortal.

## Prerequisites

### Development

* Python==3.12
* [uv](https://docs.astral.sh/uv/getting-started/installation/)
* [Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/archive/install-redis/install-redis-on-linux/)

### Docker

* [Docker Compose](https://docs.docker.com/compose/install/linux/)

## Installation

### Development

```bash
make install
```

This creates a virtual environment in `.env` that can be either activated, or indirectly by using
`uv run ...`.

```bash
source .venv/bin/activate
```

Then, start the server and worker:

```bash
# terminal 1
make serve

# terminal 2
make worker
```

## Docker

### Container registry (once)

```bash
docker run -d -p 5000:5000 --name registry registry:2
```

If the container is not running anymore (because of system restart or similar):

```bash
docker start registry
```

### Build

```bash
bash docker/build.sh
```

This builds and pushes the image to your local registry.

### Pull

```bash
docker pull localhost:5000/cbio-ingest:dev
```

### Docker Compose

To use the installation with the cBioPortal docker compose, copy the override and env file to the
cbioPortal Docker compose:

```bash
cp docker/docker-compose.override.yml ../cbioportal-docker-compose
cp docker/env.example ../cbioportal-docker-compose/.env.cbio-ingest
```

There is a script available that sets up cBioPortal from the official sources and copies the
cbio-ingest Docker files to that repository:

```bash
bash utils/install-cbioportal.sh <installation_folder>
```

This will create the <installation_folder> from where the script is called.

## Data provisioning

For the data provisioning you need to copy your panels and studies to the subfolders. Note that
cbio-ingest as well as cBioPortal should have access to the folders, so both folders should be
mounted in both containers as provided in the `docker/docker-compose.override.yml`:

```yml
services:
  cbioportal:
    volumes:
      - ./panel:/panel:ro

  api:
    volumes:
      - ./study:/app/study:ro
      - ./panel:/app/panel:ro
```

### Panels

Place them as text files flat (i.e. without folder structure) in the `panel/` directory, e.g.

```bash
ls -1 panel
data_gene_panel_impact230.txt
data_gene_panel_impact300.txt
data_gene_panel_impact341.txt
data_gene_panel_impact410.txt
data_gene_panel_impact468.txt
data_gene_panel_impact505.txt
```

### Studies

The studies should be unpacked in the `study/` directory. Only folders are read and each folder is
assumed to be a study.

```bash
ls -1 study
init.sh
lgg_ucsf_2014
lgg_ucsf_2014.tar.gz
msk_impact_2017
msk_impact_2017.tar.gz
```

## Access

The server is reachable via http://localhost:8000.

To access the API schema, navigate to http://localhost:8000/docs.

## Database Migrations

We use `alembic` to manage database migrations and keep a history of changes to the database.

A typical workflow looks like this:

```bash
# 1. change a model in models.py, then:
make db-migration msg="add new_field to study"

# 2. review the generated file in migrations/versions/
#    there might be changes needed in the downgrade() function

# 3. apply it
make db-migrate

# 4. if something's wrong
make db-rollback
```

To see the history of migrations, do:

```bash
make db-history
```

To see where in the history the database currently is, do:

```bash
bash db-current
```