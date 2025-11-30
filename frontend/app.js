// Configurações MQTT (WebSocket)
const mqttConfig = {
    host: "broker.hivemq.com",  // Troque para HiveMQ
    port: 8000,                 // A porta WebSocket do HiveMQ é 8000 (não 8080)
    path: "/mqtt",
    clientId: "WebClient_" + Math.random().toString(16).substr(2, 8),
    topics: {
        temp: "datacenter/fuzzy/temp",
        alert: "datacenter/fuzzy/alert"
    }
};

// Configurações Globais
const maxDataPoints = 60; // Máximo de pontos no gráfico
const chartData = {
    labels: [],
    temp: [],
    setpoint: [],
    power: []
};

// --- Configuração dos Gráficos (Chart.js) ---

// Gráfico de Temperatura
const tempCtx = document.getElementById('tempChart').getContext('2d');
const tempChart = new Chart(tempCtx, {
    type: 'line',
    data: {
        labels: chartData.labels,
        datasets: [
            {
                label: 'Temperatura (°C)',
                data: chartData.temp,
                borderColor: '#e94560', // Vermelho/Rosa
                backgroundColor: 'rgba(233, 69, 96, 0.1)',
                borderWidth: 2,
                tension: 0.4,
                fill: true
            },
            {
                label: 'Setpoint',
                data: chartData.setpoint,
                borderColor: '#4caf50', // Verde
                borderWidth: 2,
                borderDash: [5, 5], // Linha tracejada
                pointRadius: 0
            }
        ]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false, // Desativar animação para melhor performance em tempo real
        scales: {
            y: {
                suggestedMin: 15,
                suggestedMax: 30
            }
        }
    }
});

// Gráfico de Potência
const powerCtx = document.getElementById('powerChart').getContext('2d');
const powerChart = new Chart(powerCtx, {
    type: 'line',
    data: {
        labels: chartData.labels,
        datasets: [{
            label: 'Potência CRAC (%)',
            data: chartData.power,
            borderColor: '#00bcd4', // Ciano
            backgroundColor: 'rgba(0, 188, 212, 0.2)',
            borderWidth: 2,
            fill: true,
            tension: 0.1
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
            y: { min: 0, max: 100 }
        }
    }
});

// --- Lógica MQTT ---

// 1. CRIAR O CLIENTE (Esta linha estava a faltar!)
const client = new Paho.MQTT.Client(
    mqttConfig.host, 
    Number(mqttConfig.port), 
    mqttConfig.path, 
    mqttConfig.clientId
);

// 2. Definir os Callbacks
client.onConnectionLost = onConnectionLost;
client.onMessageArrived = onMessageArrived;

// 3. Conectar
console.log("A tentar conectar ao Broker " + mqttConfig.host + " na porta " + mqttConfig.port);
updateStatus("A conectar...", "yellow");

client.connect({
    onSuccess: onConnect,
    onFailure: onFailure,
    keepAliveInterval: 30,
    useSSL: false // Mosquitto na 8080 geralmente não usa SSL
});

// --- Funções Auxiliares ---

function onConnect() {
    console.log("Conectado com sucesso!");
    updateStatus("Conectado", "green");
    
    // Subscrever aos tópicos
    client.subscribe(mqttConfig.topics.temp);
    client.subscribe(mqttConfig.topics.alert);
}

function onFailure(e) {
    console.log("Falha na conexão: " + e.errorMessage);
    updateStatus("Erro de Conexão", "red");
    // Tentar reconectar em 5 segundos
    setTimeout(() => {
        console.log("A tentar reconectar...");
        client.connect({ onSuccess: onConnect, onFailure: onFailure });
    }, 5000);
}

function onConnectionLost(responseObject) {
    if (responseObject.errorCode !== 0) {
        console.log("Conexão perdida: " + responseObject.errorMessage);
        updateStatus("Desconectado", "red");
    }
}

function onMessageArrived(message) {
    const topic = message.destinationName;
    try {
        const payload = JSON.parse(message.payloadString);

        if (topic === mqttConfig.topics.temp) {
            updateDashboard(payload);
        } else if (topic === mqttConfig.topics.alert) {
            addAlert(payload);
        }
    } catch (e) {
        console.error("Erro ao ler JSON: ", e);
    }
}

function updateDashboard(data) {
    // Atualizar Textos
    document.getElementById("val-temp").innerText = data.temperatura ? data.temperatura.toFixed(1) : "--";
    document.getElementById("val-setpoint").innerText = data.setpoint ? data.setpoint.toFixed(1) : "--";
    document.getElementById("val-crac").innerText = data.potencia_crac ? data.potencia_crac.toFixed(0) : "--";
    document.getElementById("val-carga").innerText = data.carga_termica ? data.carga_termica.toFixed(0) : "--";
    document.getElementById("val-ext").innerText = data.temp_externa ? data.temp_externa.toFixed(1) : "--";
    
    const erroEl = document.getElementById("val-erro");
    if(erroEl) {
        erroEl.innerText = data.erro ? data.erro.toFixed(2) : "0.0";
    }

    // Barras Visuais
    const barTemp = document.getElementById("bar-temp");
    if(barTemp) barTemp.style.width = Math.min(100, (data.temperatura / 40) * 100) + '%';
    
    const barCrac = document.getElementById("bar-crac");
    if(barCrac) barCrac.style.width = data.potencia_crac + '%';

    // Gráficos
    if (chartData.labels.length > maxDataPoints) {
        chartData.labels.shift();
        chartData.temp.shift();
        chartData.setpoint.shift();
        chartData.power.shift();
    }

    chartData.labels.push(data.tempo);
    chartData.temp.push(data.temperatura);
    chartData.setpoint.push(data.setpoint);
    chartData.power.push(data.potencia_crac);

    tempChart.update();
    powerChart.update();
}

function addAlert(alertData) {
    const list = document.getElementById("alert-container"); // Note que mudei o ID para bater com o HTML que forneci antes
    if (!list) return;

    // Remove mensagem de "aguardando"
    if(list.firstElementChild && list.firstElementChild.innerText.includes("aguardar")) {
        list.innerHTML = "";
    }

    const item = document.createElement("div");
    item.className = "p-2 mb-2 rounded text-xs font-mono border-l-4 " + 
                     (alertData.tipo === 'CRITICO' ? "bg-red-900/30 border-red-500 text-red-200" : "bg-blue-900/30 border-blue-500 text-blue-200");
    
    item.innerHTML = `<strong>[${alertData.timestamp}] ${alertData.tipo}:</strong> ${alertData.mensagem}`;
    
    list.prepend(item);
    
    if (list.children.length > 50) list.removeChild(list.lastChild);
}

function updateStatus(text, color) {
    const el = document.getElementById('mqtt-status');
    if(!el) return;
    
    // Reseta classes
    el.className = "px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-2 border";
    
    if (color === 'green') {
        el.classList.add('bg-green-900/50', 'text-green-400', 'border-green-800');
        el.innerHTML = `<span class="w-2 h-2 rounded-full bg-green-500"></span> ${text}`;
    } else if (color === 'red') {
        el.classList.add('bg-red-900/50', 'text-red-400', 'border-red-800');
        el.innerHTML = `<span class="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span> ${text}`;
    } else {
        el.classList.add('bg-yellow-900/50', 'text-yellow-400', 'border-yellow-800');
        el.innerHTML = `<span class="w-2 h-2 rounded-full bg-yellow-500 animate-pulse"></span> ${text}`;
    }
}