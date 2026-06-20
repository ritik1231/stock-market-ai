from pydantic import BaseModel, ConfigDict


class PositionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticker: str
    qty: float
    avg_entry: float
    current_price: float
    unrealized_pnl: float
    market_value: float


class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    equity: float
    buying_power: float
    portfolio_value: float
    cash: float
    positions: list[PositionSchema]
    currency: str = "INR"
