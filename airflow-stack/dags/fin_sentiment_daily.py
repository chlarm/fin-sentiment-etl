from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

TZ = pendulum.timezone("Asia/Bangkok")

# The repo is mounted here by airflow-stack/docker-compose.yaml, as a sibling
# of the dags/ folder this file lives in.
PROJECT_DIR = Path(__file__).resolve().parent.parent / "project"


def on_failure_callback(context):
    """Email on task failure.

    run_daily.py already emails from its own try/except, but that can only
    catch Python exceptions — it cannot fire when the process is killed by a
    signal. Every real failure so far has been exactly that case: the runs on
    2026-07-18/19/24 all hung and were SIGTERMed (exit -15), so no alert was
    sent and three days of news went silently unfetched. Since Google News
    RSS has no historical archive, a day missed here is lost permanently,
    which makes silent failure the expensive kind.

    This callback runs in the task-runner process, which is NOT the shell the
    BashOperator sources .env.airflow into — so the credentials have to be
    loaded explicitly here. Everything is wrapped so that a problem in the
    alerting path can never mask or replace the original task failure.
    """
    ti = context.get("task_instance")
    dag_id = getattr(context.get("dag"), "dag_id", "unknown")
    task_id = getattr(ti, "task_id", "unknown")
    run_id = getattr(ti, "run_id", "unknown")
    try_number = getattr(ti, "try_number", "?")
    reason = context.get("reason") or context.get("exception") or "no reason reported"

    print(f"!!! AIRFLOW ALERT: DAG {dag_id} Task {task_id} FAILED !!!")

    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_DIR / ".env.airflow")
        if str(PROJECT_DIR) not in sys.path:
            sys.path.insert(0, str(PROJECT_DIR))

        from src.alerting import send_email_alert

        send_email_alert(
            subject=f"❌ AIRFLOW ETL FAILED — {dag_id}",
            body=(
                f"DAG: {dag_id}\n"
                f"Task: {task_id}\n"
                f"Run: {run_id}\n"
                f"Attempt: {try_number}\n"
                f"Reason: {reason}\n\n"
                "Note: news/sentiment for this run's date cannot be backfilled "
                "(Google News RSS returns current headlines only). Re-run the DAG "
                "soon to limit the gap; prices and technical indicators will catch "
                "up on their own from the full history."
            ),
        )
    except Exception as exc:  # noqa: BLE001 - never let alerting hide the real failure
        print(f"[Alert] Failed to send Airflow failure email: {exc!r}")

with DAG(
    dag_id="fin_sentiment_daily",
    schedule="0 6 * * *",  # ทุกวัน 06:00 (ปรับเปลี่ยนได้ใน Airflow UI)
    start_date=pendulum.datetime(2026, 1, 1, tz=TZ),
    catchup=False,
    default_args={
        "owner": "you",
        "retries": 3,
        "retry_delay": timedelta(minutes=5),
        # Without this, a hung run just sits there until the scheduler
        # eventually SIGTERMs it — observed on 2026-07-18/19/24, where each
        # attempt hung inside the FinBERT pipeline's Hugging Face hub call
        # (the model itself is cached; it's the revision check that stalls on
        # a bad network) and a single DAG run burned ~3 hours across retries.
        # A full 30-ticker run takes a few minutes, so 30m is generous while
        # still failing fast enough to leave room for the retries.
        "execution_timeout": timedelta(minutes=30),
        "on_failure_callback": on_failure_callback,
    },
    tags=["fin", "etl"],
) as dag:

    run_etl = BashOperator(
        task_id="run_daily_etl",
        bash_command=(
            "cd /opt/airflow/project && "
            "set -a && source .env.airflow && set +a && "
            "PYTHONPATH=/opt/airflow/project "
            "python -m src.etl.run_daily"
        ),
    )
