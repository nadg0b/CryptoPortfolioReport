import json
import os
import datetime
import ccxt
from jinja2 import Environment, FileSystemLoader
from pycoingecko import CoinGeckoAPI


api_creds = {
    'okx': {'apiKey': '', 
            'secret': '', 
            'password': ''},

    'bitget': {'apiKey': '', 
               'secret': '',
               'password': ''},

    'binance': {'apiKey': '', 
                'secret': ''},

    'bybit': {'apiKey': '',
              'secret': ''},

    'kucoin': {'apiKey': '', 
               'secret': '', 
               'password': ''},

    'mexc': {'apiKey': '', 
             'secret': ''},

    'bingx': {'apiKey': '', 
              'secret': ''},
}


with open('logo_map.json', 'r', encoding='utf-8') as f:
    logo_map = json.load(f)


def fetch_balance(exchange_name):
    exchange_class = getattr(ccxt, exchange_name)
    exchange = exchange_class(api_creds[exchange_name])
    exchange.load_markets()
    balance = exchange.fetch_balance()

    return balance


def get_balances():
    portfolio = {}
    for exchange in api_creds.keys():
        try:
            portfolio[exchange] = fetch_balance(exchange)['total']
            # print(f"{exchange.upper()} balance:")
            # print(json.dumps(balance["total"], indent=4, sort_keys=True))
            # print()

        except ccxt.NetworkError as e:
            print(type(e).__name__, e.args, 'Network error occurred (ignoring)')
        except ccxt.ExchangeError as e:
            print(type(e).__name__, e.args, 'Exchange error occurred (ignoring)')
        except ccxt.DDoSProtection as e:
            print(type(e).__name__, e.args, 'DDoS Protection (ignoring)')
        except ccxt.RequestTimeout as e:
            print(type(e).__name__, e.args, 'Request Timeout (ignoring)')
        except ccxt.ExchangeNotAvailable as e:
            print(type(e).__name__, e.args, 'Exchange Not Available due to downtime or maintenance (ignoring)')
        except ccxt.AuthenticationError as e:
            print(type(e).__name__, e.args, 'Authentication Error (missing API keys, ignoring)')
            
        except Exception as e:
            print(f'An error occurred: {e}')

        else:
            print(f"Succesfully fetched balance from {exchange}")

    # print(json.dumps(portfolio, indent=4, sort_keys=True))
    return portfolio


def get_token_prices_by_exchange(portfolio):
    prices = {}
    missing_symbols = set()
    coin_exchange_map = {}

    for exchange_name, balances in portfolio.items():
        try:
            exchange_class = getattr(ccxt, exchange_name.lower())
            exchange = exchange_class({'enableRateLimit': True})
            markets = exchange.load_markets()

            for token in balances:
                symbol = token.upper()
                pair = f"{symbol}/USDT"

                if symbol in prices:
                    continue

                if pair in markets:
                    try:
                        ticker = exchange.fetch_ticker(pair)
                        prices[symbol] = ticker['last']
                        coin_exchange_map[symbol] = exchange_name
                    except:
                        missing_symbols.add(symbol)
                else:
                    missing_symbols.add(symbol)

        except Exception as e:
            print(f"Error checking prices from {exchange_name}: {e}")

    cg = CoinGeckoAPI()
    try:
        coin_list = cg.get_coins_list()
        symbol_to_id = {coin['symbol'].upper(): coin['id'] for coin in coin_list}

        for symbol in missing_symbols:
            if symbol not in prices:
                coingecko_id = symbol_to_id.get(symbol)
                if coingecko_id:
                    data = cg.get_price(ids=coingecko_id, vs_currencies='usd')
                    if data.get(coingecko_id) and 'usd' in data[coingecko_id]:
                        prices[symbol] = data[coingecko_id]['usd']
                        coin_exchange_map[symbol] = "CoinGecko"
    except Exception as e:
        print("CoinGecko fallback failed:", e)

    return prices, coin_exchange_map


def calculate_usd_values(portfolio):
    all_prices, price_sources = get_token_prices_by_exchange(portfolio)

    detailed = {}
    grand_total = 0

    for exchange_name, balances in portfolio.items():
        token_details = {}
        exchange_total = 0

        for token, amount in balances.items():
            symbol = token.upper()
            price = all_prices.get(symbol)
            usd_value = amount * price if price else 0

            token_details[token] = {
                "amount": amount,
                "price_usd": price,
                "value_usd": usd_value,
                "source": price_sources.get(symbol, "N/A")
            }

            exchange_total += usd_value

        detailed[exchange_name] = {
            "tokens": token_details,
            "total_usd": exchange_total
        }
        grand_total += exchange_total

    return detailed, grand_total


def get_logo_filename(symbol, logo_mapping):
    for key, value in logo_mapping.items():
        token_symbol = key.split("\n")[1].strip()
        if symbol == token_symbol:
            return 'ico/'+value
    return None


def render_html_report(detailed_balances, total_usd, filename):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("report_template.html")
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    output = template.render(
        detailed_balances=detailed_balances,
        total_usd=total_usd,
        generated_at=now, 
        logo_map=logo_map,
        get_logo_filename=get_logo_filename
    )

    with open(f"{filename}.html", "w", encoding="utf-8") as f:
        f.write(output)

    print(f"Report saved to {filename}.html at {now}")


def main():
    portfolio = get_balances()
    detailed, total = calculate_usd_values(portfolio)
    render_html_report(detailed, total, 'report')


if __name__ == "__main__":
    main()