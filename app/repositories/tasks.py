from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Optional, Tuple

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection

from app.config import get_settings
from app.db.schema import task_artifacts, task_attempts, task_logs, tasks
from app.db.rows.control_plane import TaskAttemptRow, TaskRow
from app.models.types.control_plane import TaskAttemptStatus, TaskStatus
from app.repositories.utils import new_id, utc_now


class TaskRepository:
    def create_task(
        self,
        conn: Connection,
        workspace_id: str,
        run_submission_id: str,
        recipe_version_id: str,
        command: str,
        script_path: str,
        env_vars: dict,
        execution_spec: dict,
        timeout_seconds: int,
        task_kind: str = 'generic_command',
    ) -> TaskRow:
        task_id = new_id()
        now = utc_now()
        conn.execute(
            insert(tasks).values(
                id=task_id,
                workspace_id=workspace_id,
                run_submission_id=run_submission_id,
                recipe_version_id=recipe_version_id,
                task_kind=task_kind,
                status=TaskStatus.PENDING.value,
                attempt_count=0,
                command=command,
                script_path=script_path,
                env_vars=env_vars,
                execution_spec=execution_spec,
                timeout_seconds=timeout_seconds,
                created_at=now,
            )
        )
        return self.get_task_by_id(conn, task_id)

    def list_tasks(self, conn: Connection, workspace_id: str) -> list[TaskRow]:
        rows = conn.execute(
            select(tasks).where(tasks.c.workspace_id == workspace_id).order_by(tasks.c.created_at.desc())
        ).mappings().all()
        return [TaskRow.from_mapping(row) for row in rows]

    def get_task_by_id(self, conn: Connection, task_id: str) -> Optional[TaskRow]:
        row = conn.execute(select(tasks).where(tasks.c.id == task_id)).mappings().first()
        return TaskRow.from_mapping(row) if row else None

    def get_attempt_by_id(self, conn: Connection, attempt_id: str) -> Optional[TaskAttemptRow]:
        row = conn.execute(select(task_attempts).where(task_attempts.c.id == attempt_id)).mappings().first()
        return TaskAttemptRow.from_mapping(row) if row else None

    def claim_next_task(
        self,
        conn: Connection,
        workspace_id: str,
        worker_id: str,
        supported_task_kinds: list[str] | None = None,
    ) -> Optional[Tuple[TaskRow, TaskAttemptRow]]:
        query = (
            select(tasks)
            .where(tasks.c.workspace_id == workspace_id, tasks.c.status == TaskStatus.PENDING.value)
            .order_by(tasks.c.created_at.asc())
            .limit(1)
        )
        if supported_task_kinds:
            query = query.where(tasks.c.task_kind.in_(supported_task_kinds))
        candidate_row = conn.execute(query).mappings().first()
        if not candidate_row:
            return None

        candidate = TaskRow.from_mapping(candidate_row)
        now = utc_now()
        lease_seconds = get_settings().claim_lease_seconds
        lease_token = secrets.token_hex(16)
        attempt_id = new_id()
        attempt_number = candidate.attempt_count + 1
        lease_expires_at = now + timedelta(seconds=lease_seconds)

        updated = conn.execute(
            update(tasks)
            .where(tasks.c.id == candidate.id, tasks.c.status == TaskStatus.PENDING.value)
            .values(
                status=TaskStatus.CLAIMED.value,
                assigned_worker_id=worker_id,
                current_attempt_id=attempt_id,
                lease_token=lease_token,
                lease_expires_at=lease_expires_at,
                attempt_count=attempt_number,
            )
        )
        if updated.rowcount == 0:
            return None

        conn.execute(
            insert(task_attempts).values(
                id=attempt_id,
                task_id=candidate.id,
                worker_id=worker_id,
                attempt_number=attempt_number,
                status=TaskAttemptStatus.CLAIMED.value,
                lease_token=lease_token,
                last_heartbeat_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        return self.get_task_by_id(conn, candidate.id), self.get_attempt_by_id(conn, attempt_id)

    def transition_task(
        self,
        conn: Connection,
        task_id: str,
        attempt_id: str,
        lease_token: str,
        *,
        task_status: TaskStatus,
        attempt_status: TaskAttemptStatus,
        openlineage_run_id: Optional[str] = None,
        failure_reason: Optional[str] = None,
        mark_started: bool = False,
        mark_ended: bool = False,
    ) -> tuple[TaskRow, TaskAttemptRow]:
        task_row = self.get_task_by_id(conn, task_id)
        attempt_row = self.get_attempt_by_id(conn, attempt_id)
        if not task_row or not attempt_row:
            raise ValueError('task or attempt not found')
        if attempt_row.task_id != task_id or attempt_row.lease_token != lease_token:
            raise ValueError('lease token does not match task attempt')

        now = utc_now()
        task_values: dict[str, object] = {
            'status': task_status.value,
            'failure_reason': failure_reason,
        }
        attempt_values: dict[str, object] = {
            'status': attempt_status.value,
            'failure_reason': failure_reason,
            'openlineage_run_id': openlineage_run_id,
            'updated_at': now,
            'last_heartbeat_at': now,
        }
        if mark_started:
            task_values['started_at'] = now
            attempt_values['started_at'] = now
        if mark_ended:
            task_values['ended_at'] = now
            task_values['lease_expires_at'] = None
            task_values['lease_token'] = None
            attempt_values['ended_at'] = now

        conn.execute(update(tasks).where(tasks.c.id == task_id).values(**task_values))
        conn.execute(update(task_attempts).where(task_attempts.c.id == attempt_id).values(**attempt_values))
        return self.get_task_by_id(conn, task_id), self.get_attempt_by_id(conn, attempt_id)

    def update_attempt_heartbeat(self, conn: Connection, attempt_id: str) -> TaskAttemptRow:
        now = utc_now()
        conn.execute(
            update(task_attempts).where(task_attempts.c.id == attempt_id).values(last_heartbeat_at=now, updated_at=now)
        )
        return self.get_attempt_by_id(conn, attempt_id)

    def create_task_log(self, conn: Connection, attempt_id: str, stream: str, message: str, sequence: Optional[int]) -> dict:
        log_id = new_id()
        logged_at = utc_now()
        seq = sequence if sequence is not None else 0
        conn.execute(
            insert(task_logs).values(
                id=log_id,
                attempt_id=attempt_id,
                stream=stream,
                message=message,
                sequence=seq,
                logged_at=logged_at,
            )
        )
        return {
            'id': log_id,
            'attemptId': attempt_id,
            'stream': stream,
            'message': message,
            'sequence': seq,
            'loggedAt': logged_at,
        }

    def list_task_logs(self, conn: Connection, attempt_id: str) -> list[dict]:
        rows = conn.execute(
            select(task_logs)
            .where(task_logs.c.attempt_id == attempt_id)
            .order_by(task_logs.c.sequence.asc(), task_logs.c.logged_at.asc())
        ).mappings().all()
        return [
            {
                'id': row['id'],
                'attemptId': row['attempt_id'],
                'stream': row['stream'],
                'message': row['message'],
                'sequence': row['sequence'],
                'loggedAt': row['logged_at'],
            }
            for row in rows
        ]

    def create_task_artifact(
        self,
        conn: Connection,
        attempt_id: str,
        kind: str,
        name: str,
        uri: str,
        metadata: dict,
        dataset_id: Optional[str],
        dataset_version_id: Optional[str],
        model_uri: Optional[str],
    ) -> dict:
        artifact_id = new_id()
        created_at = utc_now()
        conn.execute(
            insert(task_artifacts).values(
                id=artifact_id,
                attempt_id=attempt_id,
                kind=kind,
                name=name,
                uri=uri,
                metadata_json=metadata,
                dataset_id=dataset_id,
                dataset_version_id=dataset_version_id,
                model_uri=model_uri,
                created_at=created_at,
            )
        )
        return {
            'id': artifact_id,
            'attemptId': attempt_id,
            'kind': kind,
            'name': name,
            'uri': uri,
            'metadata': metadata,
            'datasetId': dataset_id,
            'datasetVersionId': dataset_version_id,
            'modelUri': model_uri,
            'createdAt': created_at,
        }

    def list_task_artifacts(self, conn: Connection, attempt_id: str) -> list[dict]:
        rows = conn.execute(
            select(task_artifacts)
            .where(task_artifacts.c.attempt_id == attempt_id)
            .order_by(task_artifacts.c.created_at.asc())
        ).mappings().all()
        return [
            {
                'id': row['id'],
                'attemptId': row['attempt_id'],
                'kind': row['kind'],
                'name': row['name'],
                'uri': row['uri'],
                'metadata': row['metadata_json'] or {},
                'datasetId': row['dataset_id'],
                'datasetVersionId': row['dataset_version_id'],
                'modelUri': row['model_uri'],
                'createdAt': row['created_at'],
            }
            for row in rows
        ]
