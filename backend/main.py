import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import paho.mqtt.client as mqtt
import time
import json
import math
import threading

BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC_CMD = "datacenter/fuzzy/cmd"
TOPIC_RES = "datacenter/fuzzy/result"
TOPIC_STREAM = "datacenter/fuzzy/stream"
TOPIC_ALERT = "datacenter/fuzzy/alert"

simulating = False

print("A configurar Sistema Fuzzy...")
errotemp = ctrl.Antecedent(np.arange(-14, 14.1, 0.1), 'errotemp')
varerrotemp =ctrl.Antecedent(np.arange(-2, 2.1, 0.1), 'varerrotemp')
aquecedor =ctrl.Consequent(np.arange(0, 101, 1), 'aquecedor')

errotemp['MN'] = fuzz.trapmf(errotemp.universe, [-14, -14, -2,-1])
errotemp['PN'] = fuzz.trimf(errotemp.universe, [-2,-1,0])
errotemp['ZE'] = fuzz.trimf(errotemp.universe, [-1, 0, 1])
errotemp['PP'] = fuzz.trimf(errotemp.universe, [0, 1, 2])
errotemp['MP'] = fuzz.trapmf(errotemp.universe,[1, 2, 14,14])

varerrotemp['MN'] = fuzz.trapmf(varerrotemp.universe, [-2, -2, -0.2,-0.1])
varerrotemp['PN'] = fuzz.trimf(varerrotemp.universe, [-0.2,-0.1,0])
varerrotemp['ZE'] = fuzz.trimf(varerrotemp.universe, [-0.1, 0, 0.1])
varerrotemp['PP'] = fuzz.trimf(varerrotemp.universe, [0, 0.1, 0.2])
varerrotemp['MP'] = fuzz.trapmf(varerrotemp.universe,[0.1, 0.2, 2.1, 2.1])

aquecedor['MB'] = fuzz.trimf(aquecedor.universe, [0, 0, 25])
aquecedor['B'] = fuzz.trimf(aquecedor.universe, [0, 25, 50])
aquecedor['M'] = fuzz.trimf(aquecedor.universe, [25, 50, 75]) # Ponto de Estabilidade
aquecedor['A'] = fuzz.trimf(aquecedor.universe, [50, 75, 100])
aquecedor['MA'] = fuzz.trimf(aquecedor.universe, [75, 100, 100])

rules = [
    # CÉLULA 7: NOVA BASE DE REGRAS (CONTROLADOR CRAC - RESFRIAMENTO)

    # O CRAC precisa de MÁXIMA POTÊNCIA (MA) quando o ERRO for MN (Temperatura Muito ACIMA do SP)

    # --- LINHA ERRO 'MN' (Temperatura Muito ACIMA do SP) ---
    ctrl.Rule(errotemp['MN'] & varerrotemp['MN'], aquecedor['MA']),
    ctrl.Rule(errotemp['MN'] & varerrotemp['PN'], aquecedor['MA']),
    ctrl.Rule(errotemp['MN'] & varerrotemp['ZE'], aquecedor['MA']),
    ctrl.Rule(errotemp['MN'] & varerrotemp['PP'], aquecedor['A']),
    ctrl.Rule(errotemp['MN'] & varerrotemp['MP'], aquecedor['M']),

    # --- LINHA ERRO 'PN' (Temperatura Pouco ACIMA do SP) ---
    ctrl.Rule(errotemp['PN'] & varerrotemp['MN'], aquecedor['MA']),
    ctrl.Rule(errotemp['PN'] & varerrotemp['PN'], aquecedor['A']),
    ctrl.Rule(errotemp['PN'] & varerrotemp['ZE'], aquecedor['A']),
    ctrl.Rule(errotemp['PN'] & varerrotemp['PP'], aquecedor['M']),
    ctrl.Rule(errotemp['PN'] & varerrotemp['MP'], aquecedor['B']),

    # --- LINHA ERRO 'ZE' (Temperatura em Torno do SP) ---
    ctrl.Rule(errotemp['ZE'] & varerrotemp['MN'], aquecedor['B']),
    ctrl.Rule(errotemp['ZE'] & varerrotemp['PN'], aquecedor['A']),
    ctrl.Rule(errotemp['ZE'] & varerrotemp['ZE'], aquecedor['M']),  # Estabilidade
    ctrl.Rule(errotemp['ZE'] & varerrotemp['PP'], aquecedor['B']),
    ctrl.Rule(errotemp['ZE'] & varerrotemp['MP'], aquecedor['MB']),

    # --- LINHA ERRO 'PP' (Temperatura Pouco ABAIXO do SP) ---
    ctrl.Rule(errotemp['PP'] & varerrotemp['MN'], aquecedor['MB']),
    ctrl.Rule(errotemp['PP'] & varerrotemp['PN'], aquecedor['B']),
    ctrl.Rule(errotemp['PP'] & varerrotemp['ZE'], aquecedor['B']),
    ctrl.Rule(errotemp['PP'] & varerrotemp['PP'], aquecedor['M']),
    ctrl.Rule(errotemp['PP'] & varerrotemp['MP'], aquecedor['A']),

    # --- LINHA ERRO 'MP' (Temperatura Muito ABAIXO do SP) ---
    ctrl.Rule(errotemp['MP'] & varerrotemp['MN'], aquecedor['M']),
    ctrl.Rule(errotemp['MP'] & varerrotemp['PN'], aquecedor['B']),
    ctrl.Rule(errotemp['MP'] & varerrotemp['ZE'], aquecedor['MB']),
    ctrl.Rule(errotemp['MP'] & varerrotemp['PP'], aquecedor['MB']),
    ctrl.Rule(errotemp['MP'] & varerrotemp['MP'], aquecedor['MB']),
]

crac_ctrl = ctrl.ControlSystem(rules)
crac_sim = ctrl.ControlSystemSimulation(crac_ctrl)

def modelo_fisico(T_atual, P_crac, Q_est, T_ext):
    return (0.9 * T_atual) - (0.08 * P_crac) + (0.05 * Q_est) + (0.02 * T_ext) + 3.5

def on_connect(client, userdata, flags, rc):
    print(f"Conectado ao Broker (RC: {rc})")
    client.subscribe(TOPIC_CMD)

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        cmd = payload.get("cmd")
        if cmd == "controle_pontual":
            tratar_pontual(payload)
        elif cmd == "simular_24h":
            t = threading.Thread(target=tratar_simulacao, args=(payload,))
            t.start()
    except Exception as e:
        print(f"Erro: {e}")

def tratar_pontual(dados):
    try:
        e = float(dados.get("erro", 0))
        de = float(dados.get("delta_erro", 0))
        crac_sim.input['erro'] = e
        crac_sim.input['delta_erro'] = de
        try: crac_sim.compute()
        except: pass
        res = crac_sim.output.get('p_crac', 50.0)
        
        client.publish(TOPIC_RES, json.dumps({
            "tipo": "pontual", "erro": e, "p_crac": res,
            "msg": f"Cálculo: Erro {e} -> Potência {res:.1f}%"
        }))
    except: pass

def tratar_simulacao(dados):
    global simulating
    if simulating: return
    simulating = True
    print("A iniciar Simulação...")

    T_set = 22.0
    T_atual = 29.0
    erro_ant = 7.0
    T_ext_base = float(dados.get("temp_ext", 25))
    Q_base = float(dados.get("carga", 40))

    hist_temp = []
    hist_crac = []
    hist_erro = []

    for t in range(1440): # 24h
        if not simulating: break
        
        T_ext = T_ext_base + 5 * math.sin(2 * math.pi * (t - 480)/1440) + np.random.normal(0, 0.1)
        Q_est = Q_base + 15 * math.exp(-((t - 720)**2)/(300**2)) + np.random.normal(0, 0.5)
        
        erro_atual = T_atual - T_set
        delta_e = erro_atual - erro_ant
        
        crac_sim.input['erro'] = max(-10, min(10, erro_atual))
        crac_sim.input['delta_erro'] = max(-5, min(5, delta_e))
        try: crac_sim.compute()
        except: pass
        P_crac = crac_sim.output.get('p_crac', 50.0)
        
        T_prox = modelo_fisico(T_atual, P_crac, Q_est, T_ext)
        
        hist_temp.append(T_atual)
        hist_crac.append(P_crac)
        hist_erro.append(erro_atual)

        if T_atual > 26 or T_atual < 18:
            client.publish(TOPIC_ALERT, json.dumps({
                "msg": f"ALERTA: Temp {T_atual:.1f}°C (Min {t})", "tipo": "alerta"
            }))

        if t % 5 == 0:
            client.publish(TOPIC_STREAM, json.dumps({
                "t": t, "temp": round(T_atual, 2), "crac": round(P_crac, 1)
            }))
            time.sleep(0.005) 

        erro_ant = erro_atual
        T_atual = T_prox

    simulating = False
    
    stats = {
        "temp": {"min": min(hist_temp), "max": max(hist_temp), "avg": sum(hist_temp)/len(hist_temp)},
        "crac": {"min": min(hist_crac), "max": max(hist_crac), "avg": sum(hist_crac)/len(hist_crac)},
        "erro": {"min": min(hist_erro), "max": max(hist_erro), "avg": sum(hist_erro)/len(hist_erro)}
    }

    client.publish(TOPIC_RES, json.dumps({
        "tipo": "fim_simulacao", 
        "msg": "Simulação Finalizada.",
        "stats": stats
    }))
    print("Simulação concluída.")

if __name__ == "__main__":
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_forever()