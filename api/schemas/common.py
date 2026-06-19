from pydantic import BaseModel


class HealthCheck(BaseModel):
    status: str
    db: bool
    xgb_models: int
    lstm_models: int
