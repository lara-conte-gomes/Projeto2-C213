import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import paho.mqtt.client as mqtt
import time
import json
import random
import math

# --- CONFIGURAÇÃO MQTT (RF4) ---
BROKER = "broker.hivemq.com"  
PORT = 1883                         
TOPIC_CONTROL = "datacenter/fuzzy/control"
TOPIC_TEMP = "datacenter/fuzzy/temp"
TOPIC_ALERT = "datacenter/fuzzy/alert"

client = mqtt.Client()
client.connect(BROKER, PORT, 60)

# --- SISTEMA FUZZY (RF1, RF2, RF3) ---
# Antecedentes (Entradas)
erro = ctrl.Antecedent(np.arange(-10, 11, 1), 'erro')
delta_erro = ctrl.Antecedent(np.arange(-5, 6, 1), 'delta_erro')
# Simplificação: Usaremos Erro e DeltaErro para o controle principal PD Fuzzy
# Text e Qest entram no modelo físico, mas poderiam ser regras adicionais aqui.

# Consequente (Saída)
p_crac = ctrl.Consequent(np.arange(0, 101, 1), 'p_crac')

# Funções de Pertinência (RF2)
erro['negativo'] = fuzz.trapmf(erro.universe, [-10, -10, -2, 0])
erro['zero'] = fuzz.trimf(erro.universe, [-2, 0, 2])
erro['positivo'] = fuzz.trapmf(erro.universe, [0, 2, 10, 10])

delta_erro['negativo'] = fuzz.trapmf(delta_erro.universe, [-5, -5, -1, 0])
delta_erro['zero'] = fuzz.trimf(delta_erro.universe, [-1, 0, 1])
delta_erro['positivo'] = fuzz.trapmf(delta_erro.universe, [0, 1, 5, 5])

p_crac['baixa'] = fuzz.trimf(p_crac.universe, [0, 0, 50])
p_crac['media'] = fuzz.trimf(p_crac.universe, [25, 50, 75])
p_crac['alta'] = fuzz.trimf(p_crac.universe, [50, 100, 100])

# Base de Regras (RF3) - Lógica PD
rule1 = ctrl.Rule(erro['negativo'] & delta_erro['negativo'], p_crac['alta']) # Muito quente, esquentando
rule2 = ctrl.Rule(erro['negativo'] & delta_erro['zero'], p_crac['alta'])
rule3 = ctrl.Rule(erro['negativo'] & delta_erro['positivo'], p_crac['media'])
rule4 = ctrl.Rule(erro['zero'] & delta_erro['negativo'], p_crac['media'])
rule5 = ctrl.Rule(erro['zero'] & delta_erro['zero'], p_crac['media']) # Mantém
rule6 = ctrl.Rule(erro['zero'] & delta_erro['positivo'], p_crac['baixa'])
rule7 = ctrl.Rule(erro['positivo'] & delta_erro['negativo'], p_crac['media'])
rule8 = ctrl.Rule(erro['positivo'] & delta_erro['zero'], p_crac['baixa'])
rule9 = ctrl.Rule(erro['positivo'] & delta_erro['positivo'], p_crac['baixa']) # Muito frio, esfriando

crac_ctrl = ctrl.ControlSystem([rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9])
crac_sim = ctrl.ControlSystemSimulation(crac_ctrl)

# --- MODELO FÍSICO E SIMULAÇÃO (RF5, RF6) ---
def modelo_fisico(T_atual, P_crac, Q_est, T_ext):
    # Equação do PDF: T[n+1] = 0.9*T[n] - 0.08*P + 0.05*Q + 0.02*Text + 3.5
    T_next = (0.9 * T_atual) - (0.08 * P_crac) + (0.05 * Q_est) + (0.02 * T_ext) + 3.5
    return T_next

# Parâmetros Iniciais
T_atual = 22.0
T_setpoint = 22.0
erro_anterior = 0
passos_totais = 1440 # 24 horas (RF5)
velocidade_simulacao = 0.1 # Segundos entre passos (para não demorar 24h reais)

print("Iniciando Simulação do Data Center...")

for t in range(passos_totais):
    # 1. Gerar Perfis Diários (2.10.1)
    # Temperatura externa senoidal (dia/noite) + ruído
    T_ext = 25 + 5 * math.sin(2 * math.pi * t / 1440) + np.random.normal(0, 0.5)
    # Carga térmica variável (mais alta durante o dia)
    Q_est = 40 + 20 * math.sin(2 * math.pi * (t-360) / 1440) + np.random.normal(0, 2)
    Q_est = max(0, min(100, Q_est)) # Clamp 0-100

    # 2. Calcular Erros
    erro_atual = T_atual - T_setpoint # e > 0 (Quente, precisa resfriar)
    delta_e = erro_atual - erro_anterior
    
    # 3. Inferência Fuzzy
    crac_sim.input['erro'] = max(-10, min(10, erro_atual)) # Clamp nos limites do universo
    crac_sim.input['delta_erro'] = max(-5, min(5, delta_e))
    
    try:
        crac_sim.compute()
        P_crac_calc = crac_sim.output['p_crac']
    except:
        P_crac_calc = 50 # Fallback

    # 4. Atualizar Modelo Físico
    T_prox = modelo_fisico(T_atual, P_crac_calc, Q_est, T_ext)
    
    # 5. Sistema de Alertas (RF4)
    if T_atual < 18 or T_atual > 26:
        alerta = {
            "timestamp": t,
            "tipo": "CRITICO",
            "mensagem": f"Temperatura fora da faixa segura: {T_atual:.2f}°C",
            "valor": T_atual
        }
        client.publish(TOPIC_ALERT, json.dumps(alerta))
        print(f"[ALERTA] {alerta['mensagem']}")

    # 6. Publicar dados MQTT para Interface
    payload = {
        "tempo": t,
        "temperatura": round(T_atual, 2),
        "setpoint": T_setpoint,
        "potencia_crac": round(P_crac_calc, 2),
        "carga_termica": round(Q_est, 2),
        "temp_externa": round(T_ext, 2),
        "erro": round(erro_atual, 2)
    }
    client.publish(TOPIC_TEMP, json.dumps(payload))
    
    # Atualizar variáveis para próximo passo
    erro_anterior = erro_atual
    T_atual = T_prox
    
    # Log console
    if t % 10 == 0:
        print(f"Minuto {t}: Temp={T_atual:.2f}°C | CRAC={P_crac_calc:.2f}% | Ext={T_ext:.2f}°C")

    time.sleep(velocidade_simulacao)