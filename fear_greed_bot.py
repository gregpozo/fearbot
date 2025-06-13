import requests
import time
import os
import numpy as np  # Para calcular RSI

# Obtener datos desde variables de entorno (secretos de GitHub)
TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# Capital total disponible por moneda (spot)
CAPITAL_TOTAL_SPOT = 48000
# Capital total disponible para futuros
CAPITAL_TOTAL_FUTURES = 2000
# Riesgo por operación en futuros (1% del capital de futuros, dividido entre monedas)
RIESGO_POR_OPERACION_BASE = 0.01
# Apalancamiento sugerido para futuros (ajustado por moneda)
APALANCAMIENTO_BTC_ETH = 5
APALANCAMIENTO_ALTCOINS = 3

# Monedas a rastrear para precios y futuros
MONEDAS = ['avalanche-2', 'hyperliquid', 'solana', 'bitcoin', 'ondo-finance', 'sui', 'ethereum', 'jupiter']

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

def obtener_tendencia_y_rsi_por_moneda(moneda):
    try:
        # Obtener datos de precios de los últimos 60 días para SMA 50
        url = f"https://api.coingecko.com/api/v3/coins/{moneda}/market_chart?vs_currency=usd&days=60&interval=daily"
        response = requests.get(url)
        data = response.json()
        precios = [candle[1] for candle in data['prices'] if len(candle) > 1]
        if len(precios) >= 50:
            sma_50 = sum(precios[-50:]) / 50
            sma_200 = sum(precios[-200:]) / 200 if len(precios) >= 200 else 0
            precio_actual = precios[-1]
            tendencia_largo_plazo = "alcista" if precio_actual > sma_200 else "bajista"
            tendencia_medio_plazo = "alcista" if precio_actual > sma_50 else "bajista"
        else:
            tendencia_largo_plazo = tendencia_medio_plazo = "indeterminado"
            sma_50 = sma_200 = 0
            precio_actual = 0

        # Obtener datos de 4 horas para RSI (aproximado con datos horarios por limitaciones de API gratuita)
        url_4h = f"https://api.coingecko.com/api/v3/coins/{moneda}/market_chart?vs_currency=usd&days=14&interval=hourly"
        response_4h = requests.get(url_4h)
        data_4h = response_4h.json()
        precios_4h = [candle[1] for candle in data_4h['prices'] if len(candle) > 1][-14:]  # Últimos 14 períodos
        rsi = calcular_rsi(precios_4h) if len(precios_4h) >= 14 else 50  # RSI aproximado
        return tendencia_largo_plazo, tendencia_medio_plazo, precio_actual, sma_50, sma_200, rsi
    except Exception as e:
        print(f"Error al obtener tendencia y RSI para {moneda}: {e}")
        return "indeterminado", "indeterminado", 0, 0, 0, 50

def calcular_rsi(precios, periodo=14):
    if len(precios) < periodo:
        return 50
    deltas = np.diff(precios)
    seed = deltas[:periodo+1]
    up = seed[seed >= 0].sum()/periodo
    down = -seed[seed < 0].sum()/periodo
    rs = up/down if down != 0 else 0
    rsi = np.zeros_like(precios)
    rsi[:periodo] = 100. - 100./(1. + rs)
    for i in range(periodo, len(precios)):
        delta = deltas[i-1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta
        up = (up * (periodo - 1) + upval) / periodo
        down = (down * (periodo - 1) + downval) / periodo
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100./(1. + rs)
    return rsi[-1]

def obtener_precios_monedas():
    try:
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

def calcular_accion(valor_fgi):
    mensaje = f"📊 **Fear & Greed Index Actual:** {valor_fgi}\n\n"

    # Estrategia SPOT (basada en FGI)
    mensaje += "📌 **Estrategia SPOT (Todas las Monedas):**\n"
    tendencia_btc_largo_plazo, _, _, _, _, _ = obtener_tendencia_y_rsi_por_moneda('bitcoin')
    mensaje += f"📈 **Tendencia del Mercado (BTC Largo Plazo):** {tendencia_btc_largo_plazo.upper()}\n"
    if tendencia_btc_largo_plazo == "alcista":
        if valor_fgi <= 40:
            if valor_fgi > 30:
                porcentaje = 20
            elif valor_fgi > 20:
                porcentaje = 30
            else:
                porcentaje = 50
            monto = int(CAPITAL_TOTAL_SPOT * porcentaje / 100)
            mensaje += f"📉 **Miedo Detectado**\n"
            mensaje += f"🟢 **Recomendación:** Comprar {porcentaje}% (${monto}) por moneda.\n"
            mensaje += f"🎯 Estrategia de acumulación activada.\n"
        elif valor_fgi >= 70:
            if valor_fgi < 75:
                porcentaje = 25
            elif valor_fgi < 80:
                porcentaje = 35
            else:
                porcentaje = 40
            mensaje += f"📈 **Codicia Detectada**\n"
            mensaje += f"🔴 **Recomendación:** Vender {porcentaje}% de tus holdings por moneda.\n"
            mensaje += f"💰 Toma de ganancias sugerida.\n"
        else:
            mensaje += f"🟡 **Sin Acción:** FGI en rango neutral ({valor_fgi}). No se recomienda comprar ni vender.\n"
    else:
        mensaje += f"⚠️ **Advertencia:** Mercado bajista o indeterminado para BTC. Estrategia de compra desactivada.\n"

    mensaje += "\n📌 **Estrategia FUTUROS (Scalping por Moneda):** \n"
    monto_riesgo_por_moneda = int(CAPITAL_TOTAL_FUTURES * RIESGO_POR_OPERACION_BASE / len(MONEDAS))  # Riesgo dividido entre monedas
    señales = []
    for moneda in MONEDAS:
        tendencia_largo_plazo, tendencia_medio_plazo, precio_actual, sma_50, _, rsi = obtener_tendencia_y_rsi_por_moneda(moneda)
        nombre = moneda.replace('-', ' ').title()
        apalancamiento = APALANCAMIENTO_BTC_ETH if moneda in ['bitcoin', 'ethereum'] else APALANCAMIENTO_ALTCOINS
        posicion = monto_riesgo_por_moneda * apalancamiento
        señal = f"🟡 Sin Acción (RSI: {rsi:.2f}, Tendencia: {tendencia_medio_plazo})"
        
        if tendencia_medio_plazo == "alcista":
            if rsi <= 30:  # Sobreventa, oportunidad de long
                stop_loss = precio_actual * 0.98  # 2% abajo (ajustado por volatilidad)
                take_profit = precio_actual * 1.05  # 5% arriba
                señal = f"🟢 LONG (RSI: {rsi:.2f})\n   💰 Posición: ${posicion} (Riesgo: ${monto_riesgo_por_moneda}, Apalancamiento: {apalancamiento}x)\n   📉 SL: ${stop_loss:.2f} | 📈 TP: ${take_profit:.2f}"
            elif rsi >= 70 and rsi < 80:  # Sobrecompra moderada, short con precaución
                stop_loss = precio_actual * 1.02  # 2% arriba
                take_profit = precio_actual * 0.96  # 4% abajo
                señal = f"🔴 SHORT (Precaución, RSI: {rsi:.2f})\n   💰 Posición: ${posicion} (Riesgo: ${monto_riesgo_por_moneda}, Apalancamiento: {apalancamiento}x)\n   📈 SL: ${stop_loss:.2f} | 📉 TP: ${take_profit:.2f}"
        elif tendencia_medio_plazo == "bajista":
            if rsi >= 70:  # Sobrecompra, oportunidad de short
                stop_loss = precio_actual * 1.02  # 2% arriba
                take_profit = precio_actual * 0.95  # 5% abajo
                señal = f"🔴 SHORT (RSI: {rsi:.2f})\n   💰 Posición: ${posicion} (Riesgo: ${monto_riesgo_por_moneda}, Apalancamiento: {apalancamiento}x)\n   📈 SL: ${stop_loss:.2f} | 📉 TP: ${take_profit:.2f}"
            elif rsi <= 30 and rsi > 20:  # Sobreventa moderada, long con precaución
                stop_loss = precio_actual * 0.98  # 2% abajo
                take_profit = precio_actual * 1.04  # 4% arriba
                señal = f"🟢 LONG (Precaución, RSI: {rsi:.2f})\n   💰 Posición: ${posicion} (Riesgo: ${monto_riesgo_por_moneda}, Apalancamiento: {apalancamiento}x)\n   📉 SL: ${stop_loss:.2f} | 📈 TP: ${take_profit:.2f}"
        
        señales.append(f"- {nombre}: {señal}")
        time.sleep(2)  # Retraso para evitar límites de API
    
    mensaje += "\n".join(señales)

    # Agregar precios de las monedas
    precios = obtener_precios_monedas()
    mensaje += "\n💰 **Precios Actuales de Monedas (USD):**\n"
    for nombre, precio in precios.items():
        mensaje += f"- {nombre}: ${precio}\n"

    return mensaje

def main():
    send_message(CHAT_ID, "Bot iniciado. Obteniendo datos del mercado...", TOKEN)
    time.sleep(2)  # Pequeño retraso para evitar límites de API

    valor_fgi = obtener_fgi()
    mensaje = calcular_accion(valor_fgi)
    send_message(CHAT_ID, mensaje, TOKEN)

if __name__ == "__main__":
    main()
