import codecs
import os
from datetime import UTC, datetime

from rq.timeouts import JobTimeoutException
from sqlmodel import Session

import docker
from app.db import add_log, engine
from app.models import LogLevel, Panel, Status, Study
from app.validator import Validator


def mark_in_progress(entity: Study | Panel, session: Session) -> None:
    entity.status = Status.IN_PROGRESS
    add_log(entity, LogLevel.INFO, "worker", "Ingestion started.")
    session.add(entity)
    session.commit()
    session.refresh(entity)


def mark_completed(entity: Study | Panel, session: Session) -> None:
    entity.status = Status.COMPLETED
    entity.date_ingested = datetime.now(UTC)
    add_log(entity, LogLevel.INFO, "worker", "Ingestion completed.")
    session.add(entity)
    session.commit()
    session.refresh(entity)


def mark_failed(entity: Study | Panel, error_message: str, session: Session) -> None:
    entity.status = Status.FAILED
    entity.date_ingested = datetime.now(UTC)
    add_log(entity, LogLevel.ERROR, "worker", f"Ingestion failed: {error_message}")
    session.add(entity)
    session.commit()
    session.refresh(entity)


def _run_ingest(
    entity: Study | Panel, cmd: list[str], workdir: str | None, session: Session
) -> None:
    mark_in_progress(entity, session)

    client: docker.DockerClient = docker.from_env(
        timeout=int(os.getenv("JOB_TIMEOUT", "43200"))
    )  # 12 hour timeout

    try:
        container = client.containers.get(
            os.getenv("CBIOPORTAL_CONTAINER_NAME", "cbioportal-container")
        )

        add_log(entity, LogLevel.INFO, "worker", f"Running command: {' '.join(cmd)}")
        print(f"Starting ingestion with command: {' '.join(cmd)} ...")

        entity.command = " ".join(cmd)
        session.add(entity)
        session.commit()
        session.refresh(entity)

        exec_id = client.api.exec_create(
            container.id,
            cmd,
            stdout=True,
            stderr=True,
            workdir=workdir,
            environment={"PYTHONUNBUFFERED": "1"},
        )
        stream = client.api.exec_start(exec_id["Id"], stream=True)
        decoder = codecs.getincrementaldecoder("utf-8")()
        buffer = ""

        for chunk in stream:
            text = decoder.decode(chunk)
            buffer += text
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.rstrip("\r")

                if not line.strip():
                    continue

                add_log(entity, LogLevel.INFO, "docker", line)
                session.add(entity)
                session.commit()

        session.add(entity)
        session.commit()
        session.refresh(entity)

        inspect = client.api.exec_inspect(exec_id["Id"])
        exit_code = inspect["ExitCode"]

        container.reload()
        entity.cbioportal_version = (
            getattr(container, "attrs", {}).get("Config", {}).get("Image", "unknown")
        )
        session.add(entity)
        session.commit()
        session.refresh(entity)

        print(f"Finished ingestion with exit code {exit_code} (0 = success)")

        if exit_code == 0:
            print("Restarting container to apply changes ...")
            container.restart()
            print("Finished restarting container")
            add_log(entity, LogLevel.INFO, "worker", "Container restarted to apply changes.")
            mark_completed(entity, session)
        else:
            mark_failed(
                entity,
                f"Container execution failed with exit code {exit_code}",
                session,
            )

    except JobTimeoutException:
        session.rollback()
        mark_failed(entity, "Job exceeded maximum timeout", session)
        raise
    except Exception as e:
        session.rollback()
        mark_failed(entity, f"Ingestion failed: {e}", session)
        raise


def ingest_study(study_id: int) -> None:
    with Session(engine) as session:
        study = session.get(Study, study_id)

        if not study:
            raise ValueError(f"Study with ID {study_id} not found")

        try:
            validated_name = Validator().validate_folder_name(study.name)
        except ValueError as e:
            mark_failed(study, str(e), session)
            raise

        cmd = [
            "metaImport.py",
            "-u",
            "http://cbioportal:8080",
            "-s",
            f"/study/{validated_name}",
            "-o",
        ]

        _run_ingest(study, cmd, None, session)


def ingest_panel(panel_id: int) -> None:
    with Session(engine) as session:
        panel = session.get(Panel, panel_id)

        if not panel:
            raise ValueError(f"Panel with ID {panel_id} not found")

        try:
            validated_name = Validator().validate_file_name(panel.name)
        except ValueError as e:
            mark_failed(panel, str(e), session)
            raise

        cmd = [
            "./importGenePanel.pl",
            "--data",
            f"/panel/{validated_name}",
        ]

        _run_ingest(panel, cmd, "/core/scripts", session)
