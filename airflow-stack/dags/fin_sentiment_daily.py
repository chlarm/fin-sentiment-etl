from __future__ import annotations

from datetime import timedelta
import pendulum

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

TZ = pendulum.timezone("Asia/Bangkok")

def on_failure_callback(context):
    """Simple callback for failure alerts."""
    dag_id = context['dag'].dag_id
    task_id = context['task_instance'].task_id
    print(f"!!! AIRFLOW ALERT: DAG {dag_id} Task {task_id} FAILED !!!")

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
