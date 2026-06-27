import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    DATABASE_URL: str = Field("sqlite:///./desk_simulator.db")
    HOST: str = Field("127.0.0.1")
    PORT: int = Field(8000)
    
    MARKET_DATA_UPDATE_INTERVAL: float = Field(2.0)
    AUTO_HEDGE_INTERVAL: float = Field(5.0)
    
    DEFAULT_SLIPPAGE: float = Field(0.0005)
    DEFAULT_MAKER_FEE: float = Field(0.0002)
    DEFAULT_TAKER_FEE: float = Field(0.0005)
    DEFAULT_HEDGE_THRESHOLD: float = Field(0.05)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()

class DeskState:
    def __init__(self):
        self.auto_hedge_enabled = True
        self.hedge_instrument = "SPOT"
        self.hedge_threshold = 0.05

desk_state = DeskState()

