import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import paho.mqtt.client as mqtt
import json
import time
import threading
from datetime import datetime, timedelta
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DataCenterFuzzyController:
    def __init__(self):
        # Parâmetros do sistema
        self.setpoint = 22.0  # Temperatura desejada
        self.current_temp = 22.0  # Temperatura atual
        self.prev_error = 0.0  # Erro anterior para cálculo de delta_e
        self.simulation_time = 0  # Tempo de simulação em minutos
        
        # Configuração MQTT
        self.mqtt_broker = "test.mosquitto.org"
        self.mqtt_port = 1883
        self.mqtt_client = None
        self.mqtt_connected = False
        
        # Histórico para métricas
        self.temperature_history = []
        self.power_history = []
        self.alert_history = []
        
        # Inicializar sistema fuzzy
        self.setup_fuzzy_system()
        
        # Configurar MQTT
        self.setup_mqtt()
    
    def setup_fuzzy_system(self):
        """Configura o sistema de controle fuzzy"""
        
        # Definir universos de discurso
        # Erro de temperatura: -6°C a +6°C
        self.error = ctrl.Antecedent(np.arange(-6, 6.1, 0.1), 'error')
        # Variação do erro: -2°C/min a +2°C/min
        self.delta_error = ctrl.Antecedent(np.arange(-2, 2.1, 0.1), 'delta_error')
        # Temperatura externa: 10°C a 35°C
        self.external_temp = ctrl.Antecedent(np.arange(10, 35.1, 0.1), 'external_temp')
        # Carga térmica: 0% a 100%
        self.thermal_load = ctrl.Antecedent(np.arange(0, 101, 1), 'thermal_load')
        # Potência do CRAC: 0% a 100%
        self.power_output = ctrl.Consequent(np.arange(0, 101, 1), 'power_output')
        
        # Definir funções de pertinência para ERRO
        self.error['NB'] = fuzz.trimf(self.error.universe, [-6, -6, -3])  # Negativo Grande
        self.error['NS'] = fuzz.trimf(self.error.universe, [-4, -2, 0])   # Negativo Pequeno
        self.error['Z'] = fuzz.trimf(self.error.universe, [-1, 0, 1])     # Zero
        self.error['PS'] = fuzz.trimf(self.error.universe, [0, 2, 4])     # Positivo Pequeno
        self.error['PB'] = fuzz.trimf(self.error.universe, [3, 6, 6])     # Positivo Grande
        
        # Definir funções de pertinência para DELTA_ERRO
        self.delta_error['N'] = fuzz.trimf(self.delta_error.universe, [-2, -2, 0])  # Negativo
        self.delta_error['Z'] = fuzz.trimf(self.delta_error.universe, [-1, 0, 1])   # Zero
        self.delta_error['P'] = fuzz.trimf(self.delta_error.universe, [0, 2, 2])    # Positivo
        
        # Definir funções de pertinência para TEMPERATURA EXTERNA
        self.external_temp['COLD'] = fuzz.trimf(self.external_temp.universe, [10, 10, 20])   # Frio
        self.external_temp['MILD'] = fuzz.trimf(self.external_temp.universe, [15, 22, 28])   # Ameno
        self.external_temp['HOT'] = fuzz.trimf(self.external_temp.universe, [25, 35, 35])    # Quente
        
        # Definir funções de pertinência para CARGA TÉRMICA
        self.thermal_load['LOW'] = fuzz.trimf(self.thermal_load.universe, [0, 0, 40])      # Baixa
        self.thermal_load['MEDIUM'] = fuzz.trimf(self.thermal_load.universe, [20, 50, 80]) # Média
        self.thermal_load['HIGH'] = fuzz.trimf(self.thermal_load.universe, [60, 100, 100]) # Alta
        
        # Definir funções de pertinência para POTÊNCIA DE SAÍDA
        self.power_output['VL'] = fuzz.trimf(self.power_output.universe, [0, 0, 25])      # Muito Baixa
        self.power_output['L'] = fuzz.trimf(self.power_output.universe, [10, 30, 50])     # Baixa
        self.power_output['M'] = fuzz.trimf(self.power_output.universe, [30, 50, 70])     # Média
        self.power_output['H'] = fuzz.trimf(self.power_output.universe, [50, 70, 90])     # Alta
        self.power_output['VH'] = fuzz.trimf(self.power_output.universe, [75, 100, 100])  # Muito Alta
        
        # Criar base de regras
        self.setup_fuzzy_rules()
    
    def setup_fuzzy_rules(self):
        """Configura a base de regras fuzzy"""
        
        # Regras principais baseadas no erro e variação do erro
        rule1 = ctrl.Rule(self.error['NB'] | self.error['NS'], self.power_output['VL'])
        rule2 = ctrl.Rule(self.error['Z'] & self.delta_error['N'], self.power_output['L'])
        rule3 = ctrl.Rule(self.error['Z'] & self.delta_error['Z'], self.power_output['M'])
        rule4 = ctrl.Rule(self.error['Z'] & self.delta_error['P'], self.power_output['H'])
        rule5 = ctrl.Rule(self.error['PS'] | self.error['PB'], self.power_output['VH'])
        
        # Regras de ajuste baseadas na temperatura externa
        rule6 = ctrl.Rule(self.external_temp['HOT'], self.power_output['H'])
        rule7 = ctrl.Rule(self.external_temp['COLD'], self.power_output['L'])
        
        # Regras de ajuste baseadas na carga térmica
        rule8 = ctrl.Rule(self.thermal_load['HIGH'], self.power_output['VH'])
        rule9 = ctrl.Rule(self.thermal_load['LOW'], self.power_output['VL'])
        
        # Regras combinadas
        rule10 = ctrl.Rule(self.error['PS'] & self.thermal_load['HIGH'], self.power_output['VH'])
        rule11 = ctrl.Rule(self.error['Z'] & self.external_temp['HOT'] & self.thermal_load['MEDIUM'], 
                          self.power_output['H'])
        
        self.control_system = ctrl.ControlSystem([
            rule1, rule2, rule3, rule4, rule5, 
            rule6, rule7, rule8, rule9, rule10, rule11
        ])
        
        self.controller = ctrl.ControlSystemSimulation(self.control_system)
    
    def calculate_power(self, current_temp, external_temp, thermal_load):
        """Calcula a potência do CRAC usando lógica fuzzy"""
        
        # Calcular erro e variação do erro
        error = current_temp - self.setpoint
        delta_error = error - self.prev_error
        
        # Atualizar erro anterior
        self.prev_error = error
        
        try:
            # Definir entradas do sistema fuzzy
            self.controller.input['error'] = error
            self.controller.input['delta_error'] = delta_error
            self.controller.input['external_temp'] = external_temp
            self.controller.input['thermal_load'] = thermal_load
            
            # Computar a saída
            self.controller.compute()
            
            # Obter potência calculada
            power = self.controller.output['power_output']
            
            # Garantir que está no range [0, 100]
            power = max(0, min(100, power))
            
            return power
            
        except Exception as e:
            logging.error(f"Erro no cálculo fuzzy: {e}")
            # Fallback: controle proporcional simples
            return max(0, min(100, 50 + (error * 10)))
    
    def physical_model(self, current_temp, power, thermal_load, external_temp):
        """Modelo físico do data center"""
        # T[n+1] = 0.9 * T[n] - 0.08 * P_CRAC + 0.05 * Q_est + 0.02 * T_ext + 3.5
        next_temp = (0.9 * current_temp - 0.08 * power + 
                    0.05 * thermal_load + 0.02 * external_temp + 3.5)
        return next_temp
    
    def generate_external_temp(self, time_minutes):
        """Gera temperatura externa baseada em padrão senoidal com ruído"""
        # Padrão diário: base 20°C, amplitude 5°C
        base_temp = 20
        amplitude = 5
        period = 1440  # 24 horas em minutos
        
        # Componente senoidal
        sine_component = amplitude * np.sin(2 * np.pi * time_minutes / period)
        
        # Ruído aleatório
        noise = np.random.normal(0, 1)
        
        external_temp = base_temp + sine_component + noise
        return max(10, min(35, external_temp))  # Limitar entre 10°C e 35°C
    
    def generate_thermal_load(self, time_minutes):
        """Gera perfil de carga térmica baseado em padrão de uso"""
        # Padrão típico de data center: pico durante o dia, menor à noite
        hour = (time_minutes // 60) % 24
        
        if 9 <= hour <= 17:  # Horário comercial
            base_load = 70
            variation = np.random.normal(0, 10)
        elif 18 <= hour <= 22:  # Final da tarde
            base_load = 60
            variation = np.random.normal(0, 15)
        else:  # Madrugada
            base_load = 40
            variation = np.random.normal(0, 5)
        
        thermal_load = base_load + variation
        return max(0, min(100, thermal_load))
    
    def check_alerts(self, current_temp, power, external_temp, thermal_load):
        """Verifica e envia alertas se necessário"""
        alerts = []
        
        # Alertas críticos de temperatura
        if current_temp < 18 or current_temp > 26:
            alert = {
                "timestamp": datetime.now().isoformat(),
                "type": "CRITICAL",
                "message": f"Temperatura crítica: {current_temp:.1f}°C",
                "data": {
                    "temperature": current_temp,
                    "power": power,
                    "external_temp": external_temp,
                    "thermal_load": thermal_load
                },
                "severity": "CRITICAL"
            }
            alerts.append(alert)
            logging.critical(f"Alerta CRÍTICO: Temperatura {current_temp:.1f}°C")
        
        # Alertas de eficiência
        if power > 95 and len([p for p in self.power_history[-10:] if p > 95]) >= 8:
            alert = {
                "timestamp": datetime.now().isoformat(),
                "type": "EFFICIENCY",
                "message": "CRAC operando em potência máxima prolongada",
                "data": {"current_power": power},
                "severity": "HIGH"
            }
            alerts.append(alert)
            logging.warning("Alerta de EFICIÊNCIA: CRAC em potência máxima")
        
        # Alertas de estabilidade (verifica oscilações)
        if len(self.temperature_history) >= 10:
            recent_temps = self.temperature_history[-10:]
            variance = np.var(recent_temps)
            if variance > 2.0:  # Alta variância indica oscilações
                alert = {
                    "timestamp": datetime.now().isoformat(),
                    "type": "STABILITY",
                    "message": f"Oscilações excessivas detectadas (variância: {variance:.2f})",
                    "data": {"variance": variance},
                    "severity": "MEDIUM"
                }
                alerts.append(alert)
                logging.warning(f"Alerta de ESTABILIDADE: Variância {variance:.2f}")
        
        # Enviar alertas via MQTT
        for alert in alerts:
            self.send_mqtt_alert(alert)
            self.alert_history.append(alert)
        
        return alerts
    
    def setup_mqtt(self):
        """Configura cliente MQTT"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            # Tentar conectar em thread separada para não bloquear
            def connect():
                try:
                    self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
                    self.mqtt_client.loop_start()
                except Exception as e:
                    logging.warning(f"Falha na conexão MQTT: {e}. Modo simulação ativado.")
            
            mqtt_thread = threading.Thread(target=connect)
            mqtt_thread.daemon = True
            mqtt_thread.start()
            
        except Exception as e:
            logging.error(f"Erro na configuração MQTT: {e}")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback de conexão MQTT"""
        if rc == 0:
            self.mqtt_connected = True
            logging.info("Conectado ao broker MQTT")
        else:
            logging.warning(f"Falha na conexão MQTT. Código: {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback de desconexão MQTT"""
        self.mqtt_connected = False
        logging.warning("Desconectado do broker MQTT")
    
    def send_mqtt_data(self, topic_suffix, data):
        """Envia dados via MQTT"""
        if self.mqtt_connected:
            try:
                topic = f"datacenter/fuzzy/{topic_suffix}"
                self.mqtt_client.publish(topic, json.dumps(data))
            except Exception as e:
                logging.error(f"Erro ao enviar dados MQTT: {e}")
    
    def send_mqtt_alert(self, alert_data):
        """Envia alerta via MQTT"""
        self.send_mqtt_data("alert", alert_data)
    
    def send_control_data(self, control_data):
        """Envia dados de controle via MQTT"""
        self.send_mqtt_data("control", control_data)
    
    def send_temperature_data(self, temp_data):
        """Envia dados de temperatura via MQTT"""
        self.send_mqtt_data("temp", temp_data)
    
    def run_simulation_step(self, time_minutes):
        """Executa um passo de simulação"""
        # Gerar condições ambientais
        external_temp = self.generate_external_temp(time_minutes)
        thermal_load = self.generate_thermal_load(time_minutes)
        
        # Calcular potência do CRAC usando controle fuzzy
        power = self.calculate_power(self.current_temp, external_temp, thermal_load)
        
        # Aplicar modelo físico para próxima temperatura
        next_temp = self.physical_model(self.current_temp, power, thermal_load, external_temp)
        
        # Atualizar estado
        self.current_temp = next_temp
        self.simulation_time = time_minutes
        
        # Armazenar histórico
        self.temperature_history.append(self.current_temp)
        self.power_history.append(power)
        
        # Verificar alertas
        alerts = self.check_alerts(self.current_temp, power, external_temp, thermal_load)
        
        # Preparar dados para MQTT
        control_data = {
            "timestamp": datetime.now().isoformat(),
            "temperature": self.current_temp,
            "power": power,
            "external_temp": external_temp,
            "thermal_load": thermal_load,
            "setpoint": self.setpoint,
            "error": self.current_temp - self.setpoint
        }
        
        # Enviar dados via MQTT
        self.send_control_data(control_data)
        self.send_temperature_data({"temperature": self.current_temp, "timestamp": control_data["timestamp"]})
        
        return {
            "time": time_minutes,
            "temperature": self.current_temp,
            "power": power,
            "external_temp": external_temp,
            "thermal_load": thermal_load,
            "alerts": alerts
        }
    
    def run_24h_simulation(self):
        """Executa simulação completa de 24 horas"""
        logging.info("Iniciando simulação de 24 horas...")
        
        results = []
        total_steps = 1440  # 24 horas em minutos
        
        for minute in range(total_steps):
            result = self.run_simulation_step(minute)
            results.append(result)
            
            # Log a cada hora
            if minute % 60 == 0:
                hour = minute // 60
                logging.info(f"Hora {hour:02d}:00 - Temp: {result['temperature']:.2f}°C, "
                           f"Power: {result['power']:.1f}%")
            
            time.sleep(0.01)  # Pequena pausa para simulação em tempo real
        
        # Calcular métricas finais
        metrics = self.calculate_metrics()
        
        logging.info("Simulação de 24 horas concluída")
        return results, metrics
    
    def calculate_metrics(self):
        """Calcula métricas de avaliação do sistema"""
        if not self.temperature_history:
            return {}
        
        temps = np.array(self.temperature_history)
        powers = np.array(self.power_history)
        
        # Erro RMS
        errors = temps - self.setpoint
        rmse = np.sqrt(np.mean(errors ** 2))
        
        # Tempo em faixa (20-24°C)
        in_range = np.sum((temps >= 20) & (temps <= 24))
        time_in_range = (in_range / len(temps)) * 100
        
        # Consumo energético (integral da potência)
        energy_consumption = np.sum(powers) * (1/60)  # kWh assumindo 1 minuto por passo
        
        # Número de violações críticas
        critical_violations = np.sum((temps < 18) | (temps > 26))
        
        metrics = {
            "rmse": rmse,
            "time_in_range_percent": time_in_range,
            "energy_consumption_kwh": energy_consumption,
            "critical_violations": critical_violations,
            "avg_temperature": np.mean(temps),
            "avg_power": np.mean(powers),
            "max_temperature": np.max(temps),
            "min_temperature": np.min(temps)
        }
        
        logging.info(f"Métricas finais - RMSE: {rmse:.3f}, "
                   f"Tempo em faixa: {time_in_range:.1f}%, "
                   f"Violacoes: {critical_violations}")
        
        return metrics
    
    def get_system_status(self):
        """Retorna status atual do sistema"""
        return {
            "current_temperature": self.current_temp,
            "setpoint": self.setpoint,
            "simulation_time": self.simulation_time,
            "mqtt_connected": self.mqtt_connected,
            "total_alerts": len(self.alert_history)
        }


# Função principal para teste
def main():
    """Função principal para demonstrar o sistema"""
    controller = DataCenterFuzzyController()
    
    # Aguardar inicialização
    time.sleep(2)
    
    # Executar simulação de 24 horas
    results, metrics = controller.run_24h_simulation()
    
    # Exibir métricas finais
    print("\n=== MÉTRICAS FINAIS ===")
    for key, value in metrics.items():
        print(f"{key}: {value}")
    
    # Exibir resumo de alertas
    print(f"\n=== TOTAL DE ALERTAS: {len(controller.alert_history)} ===")
    for alert in controller.alert_history[-5:]:  # Últimos 5 alertas
        print(f"{alert['timestamp']} - {alert['type']}: {alert['message']}")


if __name__ == "__main__":
    main()