from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("camguard.snowflake")

SNOWFLAKE_ACCOUNT = os.getenv("SNOWFLAKE_ACCOUNT", "")
SNOWFLAKE_USER = os.getenv("SNOWFLAKE_USER", "")
SNOWFLAKE_PASSWORD = os.getenv("SNOWFLAKE_PASSWORD", "")
SNOWFLAKE_DATABASE = os.getenv("SNOWFLAKE_DATABASE", "CAMGUARD")
SNOWFLAKE_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA", "PUBLIC")
SNOWFLAKE_WAREHOUSE = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
SNOWFLAKE_ROLE = os.getenv("SNOWFLAKE_ROLE", "SYSADMIN")

_conn = None
_conn_attempted = False


def _is_configured() -> bool:
    return bool(SNOWFLAKE_ACCOUNT and SNOWFLAKE_USER and SNOWFLAKE_PASSWORD
                and not SNOWFLAKE_ACCOUNT.startswith("your-"))


def get_connection():
    global _conn, _conn_attempted
    if _conn is not None:
        return _conn
    if _conn_attempted:
        return None
    _conn_attempted = True
    if not _is_configured():
        logger.warning("Snowflake not configured – writes will be skipped")
        return None
    try:
        import snowflake.connector
        _conn = snowflake.connector.connect(
            account=SNOWFLAKE_ACCOUNT,
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA,
            warehouse=SNOWFLAKE_WAREHOUSE,
            role=SNOWFLAKE_ROLE,
        )
        return _conn
    except Exception as e:
        logger.error("Snowflake connection failed: %s", e)
        return None


def ensure_tables():
    conn = get_connection()
    if conn is None:
        return

    tables = {
        "agent_logs": """
            CREATE TABLE IF NOT EXISTS agent_logs (
                id STRING,
                camera_id STRING,
                incident_id STRING,
                ts TIMESTAMP_NTZ,
                event_kind STRING,
                payload_json VARIANT,
                dt DATE
            )
        """,
        "incident_timeline_sf": """
            CREATE TABLE IF NOT EXISTS incident_timeline_sf (
                id STRING,
                incident_id STRING,
                camera_id STRING,
                kind STRING,
                ts TIMESTAMP_NTZ,
                payload_json VARIANT,
                dt DATE
            )
        """,
        "incident_plans_sf": """
            CREATE TABLE IF NOT EXISTS incident_plans_sf (
                id STRING,
                incident_id STRING,
                version INTEGER,
                model_used STRING,
                verdict STRING,
                severity_seed INTEGER,
                confidence FLOAT,
                reasons VARIANT,
                actions VARIANT,
                replan_interval_s FLOAT,
                ts TIMESTAMP_NTZ,
                dt DATE
            )
        """,
        "action_log_sf": """
            CREATE TABLE IF NOT EXISTS action_log_sf (
                id STRING,
                incident_id STRING,
                camera_id STRING,
                action_type STRING,
                params VARIANT,
                result STRING,
                ts TIMESTAMP_NTZ,
                dt DATE
            )
        """,
        "config_suggestions_sf": """
            CREATE TABLE IF NOT EXISTS config_suggestions_sf (
                id STRING,
                camera_id STRING,
                ts TIMESTAMP_NTZ,
                reason STRING,
                confidence FLOAT,
                config_json VARIANT,
                dt DATE
            )
        """,
        "config_applied_sf": """
            CREATE TABLE IF NOT EXISTS config_applied_sf (
                id STRING,
                camera_id STRING,
                ts TIMESTAMP_NTZ,
                reason STRING,
                confidence FLOAT,
                config_json VARIANT,
                applied BOOLEAN,
                dt DATE
            )
        """,
        "chatbot_logs": """
            CREATE TABLE IF NOT EXISTS chatbot_logs (
                id STRING,
                session_id STRING,
                role STRING,
                message_text STRING,
                camera_id STRING,
                response_time_s FLOAT,
                ts TIMESTAMP_NTZ,
                dt DATE
            )
        """,
        "performance_metrics_sf": """
            CREATE TABLE IF NOT EXISTS performance_metrics_sf (
                id STRING,
                metric_type STRING,
                metric_name STRING,
                value FLOAT,
                metadata_json VARIANT,
                ts TIMESTAMP_NTZ,
                dt DATE
            )
        """,
    }

    cursor = conn.cursor()
    try:
        for table_name, ddl in tables.items():
            cursor.execute(ddl)
            logger.info("Ensured Snowflake table: %s", table_name)
    finally:
        cursor.close()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today_str() -> str:
    return _now_utc().strftime("%Y-%m-%d")


def write_timeline_event(
    event_id: str, incident_id: str, camera_id: str,
    kind: str, ts: datetime, payload: dict | None = None,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO incident_timeline_sf (id, incident_id, camera_id, kind, ts, payload_json, dt) "
            "SELECT %s, %s, %s, %s, %s, PARSE_JSON(%s), %s",
            (event_id, incident_id, camera_id, kind,
             ts.strftime("%Y-%m-%d %H:%M:%S"),
             json.dumps(payload or {}), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake timeline write failed: %s", e)
    finally:
        cursor.close()


def write_plan(
    plan_id: str, incident_id: str, version: int, model_used: str,
    verdict: str, severity_seed: int, confidence: float,
    reasons: list, actions: list, replan_interval_s: float, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO incident_plans_sf "
            "(id, incident_id, version, model_used, verdict, severity_seed, confidence, "
            "reasons, actions, replan_interval_s, ts, dt) "
            "SELECT %s, %s, %s, %s, %s, %s, %s, PARSE_JSON(%s), PARSE_JSON(%s), %s, %s, %s",
            (plan_id, incident_id, version, model_used, verdict, severity_seed,
             confidence, json.dumps(reasons), json.dumps(actions),
             replan_interval_s, ts.strftime("%Y-%m-%d %H:%M:%S"), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake plan write failed: %s", e)
    finally:
        cursor.close()


def write_action_log(
    action_id: str, incident_id: str, camera_id: str,
    action_type: str, params: dict | None, result: str | None, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO action_log_sf (id, incident_id, camera_id, action_type, params, result, ts, dt) "
            "SELECT %s, %s, %s, %s, PARSE_JSON(%s), %s, %s, %s",
            (action_id, incident_id, camera_id, action_type,
             json.dumps(params or {}), result or "",
             ts.strftime("%Y-%m-%d %H:%M:%S"), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake action log write failed: %s", e)
    finally:
        cursor.close()


def write_agent_log(
    log_id: str, camera_id: str, incident_id: str,
    event_kind: str, payload: dict | None, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO agent_logs (id, camera_id, incident_id, event_kind, ts, payload_json, dt) "
            "SELECT %s, %s, %s, %s, %s, PARSE_JSON(%s), %s",
            (log_id, camera_id, incident_id, event_kind,
             ts.strftime("%Y-%m-%d %H:%M:%S"),
             json.dumps(payload or {}), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake agent log write failed: %s", e)
    finally:
        cursor.close()


def write_config_suggestion(
    suggestion_id: str, camera_id: str, reason: str,
    confidence: float, config_json: dict, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO config_suggestions_sf (id, camera_id, ts, reason, confidence, config_json, dt) "
            "SELECT %s, %s, %s, %s, %s, PARSE_JSON(%s), %s",
            (suggestion_id, camera_id, ts.strftime("%Y-%m-%d %H:%M:%S"),
             reason, confidence, json.dumps(config_json), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake config suggestion write failed: %s", e)
    finally:
        cursor.close()


def write_config_applied(
    applied_id: str, camera_id: str, reason: str,
    confidence: float, config_json: dict, applied: bool, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO config_applied_sf (id, camera_id, ts, reason, confidence, config_json, applied, dt) "
            "SELECT %s, %s, %s, %s, %s, PARSE_JSON(%s), %s, %s",
            (applied_id, camera_id, ts.strftime("%Y-%m-%d %H:%M:%S"),
             reason, confidence, json.dumps(config_json), applied, _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake config applied write failed: %s", e)
    finally:
        cursor.close()


def write_chatbot_log(
    log_id: str, session_id: str, role: str,
    message_text: str, camera_id: str,
    response_time_s: float, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO chatbot_logs (id, session_id, role, message_text, camera_id, response_time_s, ts, dt) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (log_id, session_id, role, message_text[:2000],
             camera_id or "", response_time_s,
             ts.strftime("%Y-%m-%d %H:%M:%S"), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake chatbot log write failed: %s", e)
    finally:
        cursor.close()


def write_performance_metric(
    metric_id: str, metric_type: str, metric_name: str,
    value: float, metadata: dict | None, ts: datetime,
):
    conn = get_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO performance_metrics_sf (id, metric_type, metric_name, value, metadata_json, ts, dt) "
            "SELECT %s, %s, %s, %s, PARSE_JSON(%s), %s, %s",
            (metric_id, metric_type, metric_name, value,
             json.dumps(metadata or {}),
             ts.strftime("%Y-%m-%d %H:%M:%S"), _today_str()),
        )
    except Exception as e:
        logger.error("Snowflake performance metric write failed: %s", e)
    finally:
        cursor.close()


def read_config_suggestions(camera_id: Optional[str] = None, limit: int = 10) -> list[dict]:
    conn = get_connection()
    if conn is None:
        return []
    cursor = conn.cursor()
    try:
        if camera_id:
            cursor.execute(
                "SELECT id, camera_id, ts, reason, confidence, config_json "
                "FROM config_suggestions_sf WHERE camera_id = %s "
                "ORDER BY ts DESC LIMIT %s",
                (camera_id, limit),
            )
        else:
            cursor.execute(
                "SELECT id, camera_id, ts, reason, confidence, config_json "
                "FROM config_suggestions_sf ORDER BY ts DESC LIMIT %s",
                (limit,),
            )
        rows = cursor.fetchall()
        results = []
        for row in rows:
            results.append({
                "id": row[0],
                "camera_id": row[1],
                "ts": str(row[2]),
                "reason": row[3],
                "confidence": row[4],
                "config_json": json.loads(row[5]) if isinstance(row[5], str) else row[5],
            })
        return results
    except Exception as e:
        logger.error("Snowflake config suggestions read failed: %s", e)
        return []
    finally:
        cursor.close()
