"""India adaptation: rename broker order id, widen ticker columns, seed NSE watchlist

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-20

"""
from alembic import op

revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None

_NSE_TICKERS = [
    ("RELIANCE.NS",  "Reliance Industries",      "Energy"),
    ("HDFCBANK.NS",  "HDFC Bank",                "Banking"),
    ("ICICIBANK.NS", "ICICI Bank",               "Banking"),
    ("TCS.NS",       "Tata Consultancy Services", "IT"),
    ("INFY.NS",      "Infosys",                  "IT"),
    ("WIPRO.NS",     "Wipro",                    "IT"),
    ("SUNPHARMA.NS", "Sun Pharmaceutical",       "Pharma"),
    ("AXISBANK.NS",  "Axis Bank",                "Banking"),
    ("KOTAKBANK.NS", "Kotak Mahindra Bank",      "Banking"),
    ("BAJFINANCE.NS","Bajaj Finance",             "NBFC"),
]


def upgrade() -> None:
    # --- Widen ticker columns to fit <SYMBOL>.NS / <SYMBOL>.BO format ---
    op.execute("ALTER TABLE stocks_watchlist  ALTER COLUMN ticker TYPE VARCHAR(20)")
    op.execute("ALTER TABLE price_snapshots   ALTER COLUMN ticker TYPE VARCHAR(20)")
    op.execute("ALTER TABLE signals           ALTER COLUMN ticker TYPE VARCHAR(20)")
    op.execute("ALTER TABLE news_articles     ALTER COLUMN ticker TYPE VARCHAR(20)")
    op.execute("ALTER TABLE filing_chunks     ALTER COLUMN ticker TYPE VARCHAR(20)")
    op.execute("ALTER TABLE trades            ALTER COLUMN ticker TYPE VARCHAR(20)")

    # --- Rename alpaca_order_id → broker_order_id in trades ---
    op.execute("ALTER TABLE trades RENAME COLUMN alpaca_order_id TO broker_order_id")

    # --- Seed NSE blue-chip watchlist (skip on conflict) ---
    for ticker, company, sector in _NSE_TICKERS:
        op.execute(
            f"INSERT INTO stocks_watchlist (ticker, company, sector) "
            f"VALUES ('{ticker}', '{company}', '{sector}') "
            f"ON CONFLICT (ticker) DO NOTHING"
        )


def downgrade() -> None:
    # Remove seeded tickers
    tickers = ", ".join(f"'{t[0]}'" for t in _NSE_TICKERS)
    op.execute(f"DELETE FROM stocks_watchlist WHERE ticker IN ({tickers})")

    # Rename column back
    op.execute("ALTER TABLE trades RENAME COLUMN broker_order_id TO alpaca_order_id")

    # Narrow columns back (only if no data exceeds 10 chars)
    op.execute("ALTER TABLE trades            ALTER COLUMN ticker TYPE VARCHAR(10)")
    op.execute("ALTER TABLE filing_chunks     ALTER COLUMN ticker TYPE VARCHAR(10)")
    op.execute("ALTER TABLE news_articles     ALTER COLUMN ticker TYPE VARCHAR(10)")
    op.execute("ALTER TABLE signals           ALTER COLUMN ticker TYPE VARCHAR(10)")
    op.execute("ALTER TABLE price_snapshots   ALTER COLUMN ticker TYPE VARCHAR(10)")
    op.execute("ALTER TABLE stocks_watchlist  ALTER COLUMN ticker TYPE VARCHAR(10)")
