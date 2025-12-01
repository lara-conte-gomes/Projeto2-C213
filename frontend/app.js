const { jsPDF } = window.jspdf;

const dom = {
    in: { erro: document.getElementById('in-erro'), delta: document.getElementById('in-delta'), setpoint: document.getElementById('in-setpoint'), text: document.getElementById('in-text'), load: document.getElementById('in-load') },
    disp: { erro: document.getElementById('disp-erro'), delta: document.getElementById('disp-delta'), temp: document.getElementById('rt-temp'), crac: document.getElementById('rt-crac'), err_rt: document.getElementById('rt-erro'), alert: document.getElementById('rt-alert'), logs: document.getElementById('system-logs') },
    rep: {
        t_min: document.getElementById('rep-temp-min'), t_avg: document.getElementById('rep-temp-avg'), t_max: document.getElementById('rep-temp-max'),
        c_min: document.getElementById('rep-crac-min'), c_avg: document.getElementById('rep-crac-avg'), c_max: document.getElementById('rep-crac-max'),
        e_min: document.getElementById('rep-erro-min'), e_avg: document.getElementById('rep-erro-avg'), e_max: document.getElementById('rep-erro-max')
    }
};

let inputState = { erro: 0, delta: 0, setpoint: 22, text: 25, load: 40 };
let logHistory = []; 

dom.in.erro.oninput = (e) => { inputState.erro = e.target.value; dom.disp.erro.innerText = e.target.value; };
dom.in.delta.oninput = (e) => { inputState.delta = e.target.value; dom.disp.delta.innerText = e.target.value; };
dom.in.setpoint.onchange = (e) => inputState.setpoint = e.target.value;
dom.in.text.onchange = (e) => inputState.text = e.target.value;
dom.in.load.onchange = (e) => inputState.load = e.target.value;

function switchTab(view) {
    const tabs = ["control", "report", "mqtt", "fuzzy"];

    // Ocultar todas as views e resetar abas
    tabs.forEach(v => {
        document.getElementById(`view-${v}`).classList.add("hidden");
        document.getElementById(`tab-${v}`).className =
            "flex-1 py-3 text-sm font-bold border-b-2 border-transparent " +
            "text-slate-500 cursor-pointer text-center hover:text-slate-300";
    });

    // Mostrar apenas a aba selecionada
    document.getElementById(`view-${view}`).classList.remove("hidden");

    // Ativar estilo verde na aba selecionada
    document.getElementById(`tab-${view}`).className =
        "flex-1 py-3 text-sm font-bold border-b-2 border-green-500 " +
        "text-green-400 bg-slate-800/50 cursor-pointer text-center";
    
    // Se trocar para a aba Fuzzy, gerar gráficos
    if (view === "fuzzy" && typeof showMFCharts === "function") {
        showMFCharts();
    }
}

function plotMF(canvasId, x, mfs, title, operatingPoint = null) {
    const canvas = document.getElementById(canvasId);
    const ctx = canvas.getContext("2d");

    if (canvas.chartInstance) {
        canvas.chartInstance.destroy();
    }

    const colors = {
        MN: "#ef4444",  // vermelho
        PN: "#fb923c",  // laranja
        ZE: "#facc15",  // amarelo
        PP: "#4ade80",  // verde
        MP: "#3b82f6",  // azul

        MB: "#a78bfa",
        B: "#f472b6",
        M: "#2dd4bf",
        A: "#38bdf8",
        MA: "#c084fc"
    };

    let datasets = Object.keys(mfs).map((key) => ({
        label: key,
        data: mfs[key],
        borderWidth: 2,
        borderColor: colors[key] || "#ffffff",
        fill: false,
        tension: 0.15
    }));

    if (operatingPoint !== null) {

        const idx = nearestIndex(x, operatingPoint);
        const yValue = fuzzyValueAt(mfs, x, operatingPoint);  // valor de pertinência

        datasets.push({
            label: "Ponto de Operação",
            data: x.map((_, i) => (i === idx ? yValue : null)),
            borderColor: "#ff0000",
            pointBackgroundColor: "#ff0000",
            pointBorderColor: "#ffffff",
            pointRadius: x.map((_, i) => (i === idx ? 8 : 0)),
            showLine: false
        });
}


    canvas.chartInstance = new Chart(ctx, {
        type: "line",
        data: {
            labels: x,
            datasets: datasets
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: "#ddd" } },
                title: { display: true, text: title, color: "#fff" }
            },
            scales: {
                x: { ticks: { color: "#ccc" } },
                y: { min: 0, max: 1, ticks: { color: "#ccc" } }
            }
        }
    });
}

function showMFCharts() {
    // Valores atuais das entradas
    const e = parseFloat(inputState.erro);
    const de = parseFloat(inputState.delta);
    const saida = parseFloat(dom.disp.crac.innerText) || 0;

    // Erro
    let x1 = [];
    for (let i = -12; i <= 12; i+=0.1) x1.push(i);

    plotMF("mf-erro", x1, {
        MN: x1.map(x => trapmf(x, -12, -12, -6, -3.5)),
        PN: x1.map(x => trimf(x, -6, -3.5, 0)),
        ZE: x1.map(x => trimf(x, -3.5, 0, 3.5)),
        PP: x1.map(x => trimf(x, 0, 3.5, 6)),
        MP: x1.map(x => trapmf(x, 3.5, 6, 12, 12)),
    }, "Função de Pertinência – ERRO", e);

    // Delta Erro
    let x2 = [];
    for (let i = -2; i <= 2; i+=0.01) x2.push(i);

    plotMF("mf-delta", x2, {
        MN: x2.map(x => trapmf(x, -2, -2, -0.3, -0.1)),
        PN: x2.map(x => trimf(x, -0.3, -0.1, 0)),
        ZE: x2.map(x => trimf(x, -0.1, 0, 0.1)),
        PP: x2.map(x => trimf(x, 0, 0.1, 0.3)),
        MP: x2.map(x => trapmf(x, 0.1, 0.3, 2, 2)),
    }, "Função de Pertinência – ΔERRO", de);

    // Saída
    let x3 = [];
    for (let i = 0; i <= 100; i+=1) x3.push(i);

    plotMF("mf-saida", x3, {
        MB: x3.map(x => trimf(x, 0, 0, 25)),
        B:  x3.map(x => trimf(x, 0, 25, 50)),
        M:  x3.map(x => trimf(x, 25, 50, 75)),
        A:  x3.map(x => trimf(x, 50, 75, 100)),
        MA: x3.map(x => trimf(x, 75, 100, 100)),
    }, "Função de Pertinência – Potência CRAC", parseFloat(inputState.saida));
}

function fuzzyValueAt(mfs, x, operatingPoint) {
    let maxVal = 0;

    for (let key in mfs) {
        const mfArray = mfs[key];
        const idx = nearestIndex(x, operatingPoint);
        maxVal = Math.max(maxVal, mfArray[idx]);
    }

    return maxVal;
}

// MF helpers
function trimf(x, a, b, c) {
    if (x <= a || x >= c) return 0;
    else if (x === b) return 1;
    else if (x < b) return (x - a) / (b - a);
    else return (c - x) / (c - b);
}

function trapmf(x, a, b, c, d) {
    if (x <= a || x >= d) return 0;
    else if (x >= b && x <= c) return 1;
    else if (x > a && x < b) return (x - a) / (b - a);
    else return (d - x) / (d - c);
}

document.getElementById("tab-fuzzy").addEventListener("click", () => {
    switchTab("fuzzy");
    setTimeout(showMFCharts, 50);  // delay evita canvas não montado
});

function nearestIndex(array, value) {
    let nearest = 0;
    let minDiff = Infinity;

    array.forEach((v, i) => {
        const diff = Math.abs(v - value);
        if (diff < minDiff) {
            minDiff = diff;
            nearest = i;
        }
    });

    return nearest;
}

function addLog(msg, type='info') {
    const time = new Date().toLocaleTimeString();
    logHistory.push(`[${time}] ${msg}`);
    const div = document.createElement('div');
    div.className = type === 'alert' ? 'text-red-400 font-bold' : type === 'success' ? 'text-green-400' : 'text-slate-300';
    div.innerHTML = `<span class="opacity-50 mr-2">[${time}]</span>${msg}`;
    dom.disp.logs.prepend(div);
}

function mqttPublish() {
    if (!client.isConnected()) {
        logMQTT("ERRO: MQTT desconectado.", "red");
        return;
    }

    const topic = document.getElementById("mqtt-topic-out").value;
    const msg = document.getElementById("mqtt-msg-out").value;

    if (!topic || !msg) return;

    const message = new Paho.MQTT.Message(msg);
    message.destinationName = topic;
    client.send(message);

    logMQTT(`Publicado em ${topic}: ${msg}`, "green");
}

function mqttSubscribe() {
    const topic = document.getElementById("mqtt-topic-sub").value;
    if (!topic) return;

    client.subscribe(topic);
    logMQTT(`Subscrito em ${topic}`, "yellow");
}

function logMQTT(text, color = "white") {
    const container = document.getElementById("mqtt-log");
    if (!container) return;

    const div = document.createElement("div");
    div.style.color = color;
    div.className = "text-xs font-mono break-all";
    div.innerText = text;

    container.prepend(div);
}

function clearMqttLogs() {
    document.getElementById("mqtt-log").innerHTML =
        "<div class='text-slate-600'>Logs apagados.</div>";
}



const ctx = document.getElementById('simChart').getContext('2d');
const chart = new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [
        { label: 'Temperatura (°C)', data: [], borderColor: '#f97316', borderWidth: 2, tension: 0.4, pointRadius: 0, yAxisID: 'y' },
        { label: 'CRAC (%)', data: [], borderColor: '#3b82f6', borderWidth: 1, pointRadius: 0, yAxisID: 'y1' }
    ]},
    options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
            x: { display: false },
            y: { position: 'left', suggestedMin: 18, suggestedMax: 26, grid: { color: '#334155' } },
            y1: { position: 'right', min: 0, max: 100, grid: { display: false } }
        },
        plugins: {
            zoom: {
                zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' },
                pan: { enabled: true, mode: 'x' }
            }
        }
    }
});

function resetZoom() { chart.resetZoom(); }

function limpar() {
    chart.data.labels = []; chart.data.datasets.forEach(d => d.data = []); chart.update();
    dom.disp.temp.innerText = "--"; dom.disp.crac.innerText = "--"; dom.disp.err_rt.innerText = "--";
    logHistory = []; dom.disp.logs.innerHTML = "<div class='text-slate-500 italic'>Logs limpos.</div>";
    addLog("Interface limpa.");
}

const client = new Paho.MQTT.Client("broker.hivemq.com", 8884, "/mqtt", "Web_" + Date.now());

client.onConnectionLost = (responseObject) => {
    document.getElementById('status-badge').innerHTML = '<div class="w-2 h-2 rounded-full bg-red-500"></div> OFF';
    addLog("Conexão perdida: " + responseObject.errorMessage, "alert");
};

client.onMessageArrived = (msg) => {
    logMQTT(`Recebido de ${msg.destinationName}: ${msg.payloadString}`, "cyan");

    try {
        const payload = JSON.parse(msg.payloadString);
        const topic = msg.destinationName;

        /* -----------------------------
            STREAM → gráfico principal
        ------------------------------ */
        if (topic.includes("stream")) {
            
            const setpoint = parseFloat(dom.in.setpoint.value) || 22;

            // Atualiza painel
            dom.disp.temp.innerText = payload.temp.toFixed(1);
            dom.disp.crac.innerText = payload.crac.toFixed(1);
            dom.disp.err_rt.innerText = (payload.temp - setpoint).toFixed(1);

            inputState.saida = payload.crac;

            // --- eixo X com contador, e não horas ---
            chart.data.labels.push(chart.data.labels.length);

            // Temperatura
            chart.data.datasets[0].data.push(payload.temp);

            // CRAC
            chart.data.datasets[1].data.push(payload.crac);

            // Mantém somente 200 pontos
            if (chart.data.labels.length > 200) {
                chart.data.labels.shift();
                chart.data.datasets.forEach(d => d.data.shift());
            }

            chart.update();
        }

        /* ---------------------------------------
           RESULT → ponto de operação nos MF
        ---------------------------------------- */
        if (topic.includes("result")) {

            dom.disp.crac.innerText = payload.p_crac.toFixed(1);

            inputState.saida = payload.p_crac;

            // Atualiza tabela
            if (payload.rules) {
                const tbody = document.querySelector("#rules-table tbody");
                tbody.innerHTML = "";

                payload.rules.forEach(r => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td class="p-2">${r.rule_id}</td>
                        <td class="p-2">${r.erro}</td>
                        <td class="p-2">${r.delta}</td>
                        <td class="p-2">${r.activ.toFixed(3)}</td>
                        <td class="p-2">${r.saida}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        }

        /* ---------------------------------------
           ALERTAS
        ---------------------------------------- */
        if (topic.includes("alert")) {
            dom.disp.alert.innerText = payload.msg;

            if (payload.tipo === "alerta") {
                dom.disp.alert.className = "text-sm font-bold mt-2 text-red-400 animate-pulse";
            } else {
                dom.disp.alert.className = "text-sm font-bold mt-2 text-green-400";
            }
        }

    } catch (e) {
        console.error("Erro ao processar mensagem MQTT:", e);
        logMQTT("Erro ao processar mensagem: " + e, "red");
    }
};

function sendCmd(cmd) {
    if (!client.isConnected()) {
        addLog("Erro: MQTT desconectado", "alert");
        return;
    }
    let payload = { cmd: cmd };
    if (cmd === 'controle_pontual') { 
        payload.erro = inputState.erro; 
        payload.delta_erro = inputState.delta; 
    }
    else if (cmd === 'simular_24h') { 
        limpar(); 
        payload.temp_ext = inputState.text;   // T_ext base
        payload.carga = inputState.load;      // Q_est base
        payload.setpoint = inputState.setpoint;                // aqui você escolhe: 16, 22, 25 ou 32
        addLog("A iniciar simulação...");
    }
    
    const message = new Paho.MQTT.Message(JSON.stringify(payload));
    message.destinationName = "datacenter/fuzzy/cmd";
    client.send(message);
}

function generatePDF() {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text("Relatório de Controle Fuzzy", 14, 20);
    doc.setFontSize(10);
    doc.text(`Data: ${new Date().toLocaleString()}`, 14, 28);

    doc.setFontSize(14);
    doc.text("Entradas", 14, 40);
    doc.autoTable({
        startY: 45,
        head: [['Parâmetro', 'Valor']],
        body: [
            ['Temp. Externa', `${inputState.text} °C`],
            ['Carga Térmica', `${inputState.load} %`]
        ]
    });

    doc.text("Estatísticas (24h)", 14, doc.lastAutoTable.finalY + 15);
    doc.autoTable({
        startY: doc.lastAutoTable.finalY + 20,
        head: [['Variável', 'Mínimo', 'Médio', 'Máximo']],
        body: [
            ['Temperatura', dom.rep.t_min.innerText, dom.rep.t_avg.innerText, dom.rep.t_max.innerText],
            ['Potência CRAC', dom.rep.c_min.innerText, dom.rep.c_avg.innerText, dom.rep.c_max.innerText],
            ['Erro', dom.rep.e_min.innerText, dom.rep.e_avg.innerText, dom.rep.e_max.innerText]
        ]
    });

    const canvasImg = document.getElementById('simChart').toDataURL("image/png", 1.0);
    doc.text("Gráfico", 14, doc.lastAutoTable.finalY + 15);
    doc.addImage(canvasImg, 'PNG', 14, doc.lastAutoTable.finalY + 20, 180, 80);

    let finalY = doc.lastAutoTable.finalY + 110;
    doc.text("Logs Recentes", 14, finalY);
    const recentLogs = logHistory.slice(-20).map(l => [l]); 
    doc.autoTable({ startY: finalY + 5, body: recentLogs });

    doc.save("relatorio_fuzzy.pdf");
}

client.connect({ 
    useSSL: true,
    onSuccess: () => {
        document.getElementById('status-badge').innerHTML = '<div class="w-2 h-2 rounded-full bg-green-500"></div> ON';
        addLog("Conectado ao Broker!", "success");
        client.subscribe("datacenter/fuzzy/#");
    },
    onFailure: (e) => {
        addLog("Falha na conexão: " + e.errorMessage, "alert");
    }
});