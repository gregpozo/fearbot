import requests
import time
import os

# Obtener datos desde variables de entorno (secretos de GitHub)
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Capital total disponible por moneda
CAPITAL_TOTAL = 10000

# Monedas a rastrear
MONEDAS = ['avalanche-2', 'hyperliquid', 'solana', 'bitcoin', 'ondo-finance', 'sui', 'ethereum']

def send_message(chat_id, text, token):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    response = requests.post(url, json=payload)
    print(f"Respuesta de la API: {response.status_code}, {response.json()}")  # Depuración
    return response

def obtener_fgi():
    url = "https://api.alternative.me/fng/?limit=1"
    response = requests.get(url)
    data = response.json()
    valor = int(data['data'][0]['value'])
    return valor

def obtener_tendencia():
    try:
        # Obtener datos de precios de Bitcoin de los últimos 200 días
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=200&interval=daily"
        response = requests.get(url)
        data = response.json()
        precios = [candle[1] for candle in data['prices'] if len(candle) > 1]  # Precio de cierre
        if len(precios) >= 200:
            sma_200 = sum(precios[-200:]) / 200
            precio_actual = precios[-1]
            tendencia = "alcista" if precio_actual > sma_200 else "bajista"
            return tendencia, precio_actual, sma_200
        else:
            return "indeterminado", 0, 0
    except Exception as e:
        print(f"Error al obtener tendencia: {e}")
        return "indeterminado", 0, 0

def obtener_precios_monedas():
    try:
        # Obtener precios actuales de las monedas
        ids = ','.join(MONEDAS)
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        response = requests.get(url)
        data = response.json()
        precios = {}
        for moneda in MONEDAS:
            nombre = moneda.replace('-', ' ').title()
            precio = data.get(moneda, {}).get('usd', 'No disponible')
            precios[nombre] = precio
        return precios
    except Exception as e:
        print(f"Error al obtener precios: {e}")
        return {}

def calcular_accion(valor_fgi, tendencia):
    mensaje = f"📊 **Fear & Greed Index Actual:** {valor_fgi}\n"
    mensaje += f"📈 **Tendencia del Mercado (BTC):** {tendencia.upper()}\n\n"

    # Agregar recomendación basada en FGI solo si el mercado es alcista
    if tendencia == "alcista":
        # 🟢 COMPRAR
        if valor_fgi <= 40:
            if valor_fgi > 30:
                porcentaje = 20
            elif valor_fgi > 20:
                porcentaje = 30
            else:
                porcentaje = 50
            monto = int(CAPITAL_TOTAL * porcentaje / 100)
            mensaje += f"📉 **Miedo Detectado**\n"
            mensaje += f"🟢 **Recomendación:** Comprar {porcentaje}% (${monto}) por moneda.\n"
            mensaje += f"🎯 Estrategia de acumulación activada.\n\n"
        # 🔴 VENDER
        elif valor_fgi >= 70:
            if valor_fgi < 75:
                porcentaje = 25
            elif valor_fgi < 80:
                porcentaje = 35
            else:
                porcentaje = 40
            mensaje += f"📈 **Codicia Detectada**\n"
            mensaje += f"🔴 **Recomendación:** Vender {porcentaje}% de tus holdings por moneda.\n"
            mensaje += f"💰 Toma de ganancias sugerida.\n\n"
        else:
            mensaje += f"🟡 **Sin Acción:** FGI en rango neutral ({valor_fgi}). No se recomienda comprar ni vender.\n\n"
    else:
        mensaje += f"⚠️ **Advertencia:** Mercado bajista o indeterminado. Estrategia de compra desactivada.\n\n"

    # Agregar precios de las monedas
    precios = obtener_precios_monedas()
    mensaje += "💰 **Precios Actuales de Monedas (USD):**\n"
    for nombre, precio in precios.items():
        mensaje += f"- {nombre}: ${precio}\n"

    return mensaje

def main():
    # Prueba inicial de conexión
    send_message(CHAT_ID, "Bot iniciado. Obteniendo datos del mercado...", TOKEN)
    time.sleep(2)  # Pequeño retraso para evitar límites de API

    # Obtener datos
    valor_fgi = obtener_fgi()
    tendencia, precio_btc, sma_200 = obtener_tendencia()
    print(f"FGI: {valor_fgi}, Tendencia: {tendencia}, Precio BTC: {precio_btc}, SMA 200: {sma_200}")

    # Generar y enviar mensaje completo
    mensaje = calcular_accion(valor_fgi, tendencia)
    send_message(CHAT_ID, mensaje, TOKEN)

if __name__ == "__main__":
    main()
