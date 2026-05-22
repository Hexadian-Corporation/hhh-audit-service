import json
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode


class Settings(BaseSettings):
    log_level: str = "INFO"
    mongo_uri: str = "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&readPreference=nearest"
    mongo_db: str = "hhh_audit"
    host: str = "0.0.0.0"
    port: int = 8011
    auth_jwks_url: Annotated[str, Field(min_length=1)]
    auth_issuer: Annotated[str, Field(min_length=1)]
    auth_audiences: Annotated[list[str], NoDecode]
    auth_leeway_seconds: Annotated[int, Field(ge=0)] = 30
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000", "http://localhost:3001"]
    retention_days: Annotated[int, Field(ge=1)] = 365
    events_mongo_uri: str = "mongodb://mongo1:27017,mongo2:27017,mongo3:27017/?replicaSet=rs0&readPreference=nearest"
    events_db: str = "hhh_events"
    events_collection: str = "events"
    subscriber_id: str = "hhh-audit-service"

    model_config = {
        "env_prefix": "HHH_AUDIT_",
        "populate_by_name": True,
        "frozen": True,
    }

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        v_upper = v.upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if v_upper not in valid:
            raise ValueError(f"Invalid log_level: {v}. Must be one of {valid}.")
        return v_upper

    @field_validator("auth_audiences", mode="before")
    @classmethod
    def parse_audiences(cls, v):
        env = "HHH_AUDIT_AUTH_AUDIENCES"
        if isinstance(v, str):
            if v.lstrip().startswith("["):
                try:
                    val = json.loads(v)
                    if isinstance(val, list):
                        if not val:
                            raise ValueError(f"{env} parsed as JSON array but is empty.")
                        return val
                    else:
                        raise ValueError(f"{env} JSON-encoded value must be a list.")
                except json.JSONDecodeError:
                    # fall through to comma-split
                    pass
            # comma-split
            result = [a.strip() for a in v.split(",") if a.strip()]
            if not result:
                raise ValueError(f"{env} provided as a string with no valid entries.")
            return result
        elif isinstance(v, list):
            if not v:
                raise ValueError(f"{env} provided as an empty list.")
            return v
        else:
            raise ValueError(f"{env} must be a string or a list of strings.")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        env = "HHH_AUDIT_CORS_ORIGINS"
        default = ["http://localhost:3000", "http://localhost:3001"]
        if v is None:
            return default
        if isinstance(v, str):
            if v.lstrip().startswith("["):
                try:
                    val = json.loads(v)
                    if isinstance(val, list):
                        if not val:
                            raise ValueError(f"{env} parsed as JSON array but is empty.")
                        return val
                    else:
                        raise ValueError(f"{env} JSON-encoded value must be a list.")
                except json.JSONDecodeError:
                    pass
            result = [a.strip() for a in v.split(",") if a.strip()]
            if not result:
                raise ValueError(f"{env} provided as a string with no valid entries.")
            return result
        elif isinstance(v, list):
            if not v:
                raise ValueError(f"{env} provided as an empty list.")
            return v
        else:
            raise ValueError(f"{env} must be a string or a list of strings.")
