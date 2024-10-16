from airflow import DAG
from airflow.models import Variable
from airflow.decorators import task
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook

from datetime import timedelta
from datetime import datetime
import snowflake.connector
import requests

def return_snowflake_conn():
    hook = SnowflakeHook(snowflake_conn_id='snowflake_conn')
    conn = hook.get_conn()
    return conn.cursor()


@task
def extract(symbol, vantage_api_key):
    url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={vantage_api_key}'
    f = requests.get(url)
    return f.json()

@task
def transform(data):
  results = []
  for d in data["Time Series (Daily)"]:
    stock_info=data["Time Series (Daily)"][d]
    stock_info["date"]=d
    results.append(data["Time Series (Daily)"][d])
  return results

@task
def load_records(cursor, table, results, symbol):
  try:
    cursor.execute(f"CREATE OR REPLACE TABLE {table} (date DATE UNIQUE, open float, high float, low float, close float, volume float, symbol string)")
    cursor.execute("COMMIT;")
  except Exception as e:
    cursor.execute("ROLLBACK;")
    print(f"Error: {e}")

  for r in results:
    date = r["date"]
    open = r["1. open"]
    high = r["2. high"]
    low = r["3. low"]
    close = r["4. close"]
    volume = r["5. volume"]
    insert_sql = f"INSERT INTO {table} (date, open, high, low, close, volume, symbol) VALUES ('{date}',{open}, {high}, {low}, {close}, {volume}, '{symbol}')"
    print(insert_sql)
    try:
      cursor.execute(insert_sql)
      cursor.execute("COMMIT;")
    except Exception as e:
      cursor.execute("ROLLBACK;")
      print(f"Error: {e}")

with DAG(
    dag_id = 'stockData',
    start_date = datetime(2024,10,10),
    catchup=False,
    tags=['ETL'],
    schedule = '*/15 * * * *'
) as dag:
    target_table = "dev.raw_data.stock_data"
    api_key = Variable.get("vantage_api_key")
    symbol = Variable.get("symbol")
    cursor = return_snowflake_conn()

    data = extract(symbol, api_key)
    lines = transform(data)
    load_records(cursor, target_table, lines, symbol)
