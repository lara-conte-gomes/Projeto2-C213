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

erro = ctrl.Antecedent(np.arange(-14, 14.1, 0.1), 'erro')
delta_erro = ctrl.Antecedent(np.arange(-2, 2.1, 0.1), 'delta_erro')
p_crac = ctrl.Consequent(np.arange(0, 101, 1), 'p_crac')

erro['MN'] = fuzz.trapmf(erro.universe, [-14, -14, -2, -1])
erro['PN'] = fuzz.trimf(erro.universe, [-2, -1, 0])
erro['ZE'] = fuzz.trimf(erro.universe, [-1, 0, 1])
erro['PP'] = fuzz.trimf(erro.universe, [0, 1, 2])
erro['MP'] = fuzz.trapmf(erro.universe, [1, 2, 14, 14])

delta_erro['MN'] = fuzz.trapmf(delta_erro.universe, [-2, -2, -0.2, -0.1])
delta_erro['PN'] = fuzz.trimf(delta_erro.universe, [-0.2, -0.1, 0])
delta_erro['ZE'] = fuzz.trimf(delta_erro.universe, [-0.1, 0, 0.1])
delta_erro['PP'] = fuzz.trimf(delta_erro.universe, [0, 0.1, 0.2])
delta_erro['MP'] = fuzz.trapmf(delta_erro.universe, [0.1, 0.2, 2.1, 2.1])

p_crac['MB'] = fuzz.trimf(p_crac.universe, [0, 0, 25])
p_crac['B'] = fuzz.trimf(p_crac.universe, [0, 25, 50])
p_crac['M'] = fuzz.trimf(p_crac.universe, [25, 50, 75])
p_crac['A'] = fuzz.trimf(p_crac.universe, [50, 75, 100])
p_crac['MA'] = fuzz.trimf(p_crac.universe, [75, 100, 100])

rules = [
    ctrl.Rule(erro['MN'] & delta_erro['MN'], p_crac['MA']),
    ctrl.Rule(erro['MN'] & delta_erro['PN'], p_crac['MA']),
    ctrl.Rule(erro['MN'] & delta_erro['ZE'], p_crac['MA']),
    ctrl.Rule(erro['MN'] & delta_erro['PP'], p_crac['A']),
    ctrl.Rule(erro['MN'] & delta_erro['MP'], p_crac['M']),

    ctrl.Rule(erro['PN'] & delta_erro['MN'], p_crac['MA']),
    ctrl.Rule(erro['PN'] & delta_erro['PN'], p_crac['A']),
    ctrl.Rule(erro['PN'] & delta_erro['ZE'], p_crac['A']),
    ctrl.Rule(erro['PN'] & delta_erro['PP'], p_crac['M']),
    ctrl.Rule(erro['PN'] & delta_erro['MP'], p_crac['B']),

    ctrl.Rule(erro['ZE'] & delta_erro['MN'], p_crac['B']),
    ctrl.Rule(erro['ZE'] & delta_erro['PN'], p_crac['A']),
    ctrl.Rule(erro['ZE'] & delta_erro['ZE'], p_crac['M']),
    ctrl.Rule(erro['ZE'] & delta_erro['PP'], p_crac['B']),
    ctrl.Rule(erro['ZE'] & delta_erro['MP'], p_crac['MB']),

    ctrl.Rule(erro['PP'] & delta_erro['MN'], p_crac['MB']),
    ctrl.Rule(erro['PP'] & delta_erro['PN'], p_crac['B']),
    ctrl.Rule(erro['PP'] & delta_erro['ZE'], p_crac['B']),
    ctrl.Rule(erro['PP'] & delta_erro['PP'], p_crac['M']),
    ctrl.Rule(erro['PP'] & delta_erro['MP'], p_crac['A']),

    ctrl.Rule(erro['MP'] & delta_erro['MN'], p_crac['M']),
    ctrl.Rule(erro['MP'] & delta_erro['PN'], p_crac['B']),
    ctrl.Rule(erro['MP'] & delta_erro['ZE'], p_crac['MB']),
    ctrl.Rule(erro['MP'] & delta_erro['PP'], p_crac['MB']),
    ctrl.Rule(erro['MP'] & delta_erro['MP'], p_crac['MB']),
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
        print(f"Erro msg: {e}")

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
    except Exception as e: 
        print(f"Erro pontual: {e}")

def tratar_simulacao(dados):
    global simulating
    if simulating: return
    simulating = True
    print("A iniciar Simulação...")

    T_set = 22.0
    T_atual = 22.0
    erro_ant = 0
    T_ext_base = float(dados.get("temp_ext", 25))
    Q_base = float(dados.get("carga", 40))

    hist_temp = []
    hist_crac = []
    hist_erro = []

    for t in range(1440): 
        if not simulating: break
        
        T_ext = T_ext_base + 5 * math.sin(2 * math.pi * (t - 480)/1440) + np.random.normal(0, 0.1)
        Q_est = Q_base + 15 * math.exp(-((t - 720)**2)/(300**2)) + np.random.normal(0, 0.5)
        
        erro_atual = T_atual - T_set
        delta_e = erro_atual - erro_ant
        
        crac_sim.input['erro'] = max(-14, min(14, erro_atual))
        crac_sim.input['delta_erro'] = max(-2, min(2, delta_e))
        
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
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except:
        pass