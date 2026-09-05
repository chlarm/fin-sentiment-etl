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
    sent and three days of news went silently unfetched — and nobody knew for
    days, which is what makes silent failure the expensive kind.

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
                "Note: re-run the DAG soon. Prices and technical indicators "
                "rebuild themselves from full history. News is recoverable too "
                "— the RSS lookback reaches back ~90 days — but each query "
                "returns a capped ~100 entries, so the longer the gap, the "
                "thinner the recovered coverage for the days inside it."
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
        # Two, not three. Every failure so far repeated identically on retry,
        # so extra attempts only delayed the alert and burned hours.
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": on_failure_callback,
    },
    tags=["fin", "etl"],
) as dag:

    def etl_stage(task_id: str, stage: str, timeout_minutes: int) -> BashOperator:
        """One ETL stage as its own task.

        `python -u` is not cosmetic. Python buffers stdout when it is a pipe,
        so when a task was SIGTERMed the entire log was discarded unwritten:
        the runs that failed nightly from 2026-07-24 onward left nothing behind
        but a Hugging Face warning on stderr, and there was no way to tell
        which stage had even been reached. Unbuffered output is what makes the
        next failure diagnosable.

        Timeouts are per stage and sized against measured runtime — the full
        pipeline takes about a minute for 30 tickers — so a stall is caught in
        minutes rather than after burning the whole night across retries.
        """
        return BashOperator(
            task_id=task_id,
            bash_command=(
                "cd /opt/airflow/project && "
                "set -a && source .env.airflow && set +a && "
                "PYTHONPATH=/opt/airflow/project "
                f"python -u -m src.etl.run_daily --stage {stage}"
            ),
            execution_timeout=timedelta(minutes=timeout_minutes),
        )

    # Prices and news are deliberately independent: running them as one task
    # meant a stall in the slow, model-loading half also rolled back the fast,
    # reliable one. News still deserves the larger timeout — it now scores a
    # 90-day lookback rather than 7 (see src/config.py), though only articles
    # not already stored are passed to FinBERT.
    fetch_prices = etl_stage("fetch_prices", "prices", timeout_minutes=15)
    fetch_news = etl_stage("fetch_news", "news", timeout_minutes=30)

    # Reports on the database rather than on this run, so the summary is still
    # accurate when one of the two above failed. Runs regardless of their
    # outcome for exactly that reason: a failed night is when the report
    # matters most.
    data_quality = etl_stage("data_quality", "dq", timeout_minutes=10)
    data_quality.trigger_rule = "all_done"

    [fetch_prices, fetch_news] >> data_quality
