const { jsPDF } = window.jspdf;

const dom = {
    in: { erro: document.getElementById('in-erro'), delta: document.getElementById('in-delta'), text: document.getElementById('in-text'), load: document.getElementById('in-load') },
    disp: { erro: document.getElementById('disp-erro'), delta: document.getElementById('disp-delta'), temp: document.getElementById('rt-temp'), crac: document.getElementById('rt-crac'), err_rt: document.getElementById('rt-erro'), alert: document.getElementById('rt-alert'), logs: document.getElementById('system-logs') },
    rep: {
        t_min: document.getElementById('rep-temp-min'), t_avg: document.getElementById('rep-temp-avg'), t_max: document.getElementById('rep-temp-max'),
        c_min: document.getElementById('rep-crac-min'), c_avg: document.getElementById('rep-crac-avg'), c_max: document.getElementById('rep-crac-max'),
        e_min: document.getElementById('rep-erro-min'), e_avg: document.getElementById('rep-erro-avg'), e_max: document.getElementById('rep-erro-max')
    }
};

let inputState = { erro: 0, delta: 0, text: 25, load: 40 };
let logHistory = []; 

dom.in.erro.oninput = (e) => { inputState.erro = e.target.value; dom.disp.erro.innerText = e.target.value; };
dom.in.delta.oninput = (e) => { inputState.delta = e.target.value; dom.disp.delta.innerText = e.target.value; };
dom.in.text.onchange = (e) => inputState.text = e.target.value;
dom.in.load.onchange = (e) => inputState.load = e.target.value;

function switchTab(view) {
    document.getElementById('view-control').classList.add('hidden');
    document.getElementById('view-report').classList.add('hidden');
    document.getElementById('tab-control').className = "flex-1 py-3 text-sm font-bold border-b-2 border-transparent text-slate-500 cursor-pointer text-center hover:text-slate-300";
    document.getElementById('tab-report').className = "flex-1 py-3 text-sm font-bold border-b-2 border-transparent text-slate-500 cursor-pointer text-center hover:text-slate-300";
    
    document.getElementById('view-' + view).classList.remove('hidden');
    document.getElementById('tab-' + view).className = "flex-1 py-3 text-sm font-bold border-b-2 border-green-500 text-green-400 bg-slate-800/50 cursor-pointer text-center";
}

function addLog(msg, type='info') {
    const time = new Date().toLocaleTimeString();
    logHistory.push(`[${time}] ${msg}`);
    const div = document.createElement('div');
    div.className = type === 'alert' ? 'text-red-400 font-bold' : type === 'success' ? 'text-green-400' : 'text-slate-300';
    div.innerHTML = `<span class="opacity-50 mr-2">[${time}]</span>${msg}`;
    dom.disp.logs.prepend(div);
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

const client = new Paho.MQTT.Client("broker.hivemq.com", 8000, "/mqtt", "Web_" + Date.now());

client.onConnectionLost = (responseObject) => {
    document.getElementById('status-badge').innerHTML = '<div class="w-2 h-2 rounded-full bg-red-500"></div> OFF';
    addLog("Conexão perdida: " + responseObject.errorMessage, "alert");
};

client.onMessageArrived = (msg) => {
    try {
        const p = JSON.parse(msg.payloadString);
        const topic = msg.destinationName;

        if (topic.includes("result")) {
            if (p.tipo === "pontual") {
                addLog(p.msg, "success");
                dom.disp.crac.innerText = p.p_crac.toFixed(1);
            } else if (p.tipo === "fim_simulacao") {
                addLog("Simulação finalizada.", "success");
                if(p.stats) {
                    dom.rep.t_min.innerText = p.stats.temp.min.toFixed(2);
                    dom.rep.t_avg.innerText = p.stats.temp.avg.toFixed(2);
                    dom.rep.t_max.innerText = p.stats.temp.max.toFixed(2);
                    dom.rep.c_min.innerText = p.stats.crac.min.toFixed(1);
                    dom.rep.c_avg.innerText = p.stats.crac.avg.toFixed(1);
                    dom.rep.c_max.innerText = p.stats.crac.max.toFixed(1);
                    dom.rep.e_min.innerText = p.stats.erro.min.toFixed(2);
                    dom.rep.e_avg.innerText = p.stats.erro.avg.toFixed(2);
                    dom.rep.e_max.innerText = p.stats.erro.max.toFixed(2);
                }
            }
        } else if (topic.includes("stream")) {
            chart.data.labels.push(p.t);
            chart.data.datasets[0].data.push(p.temp);
            chart.data.datasets[1].data.push(p.crac);
            chart.update('none');
            
            dom.disp.temp.innerText = p.temp.toFixed(1);
            dom.disp.crac.innerText = p.crac.toFixed(0);
            dom.disp.err_rt.innerText = (p.temp - 22).toFixed(1);
        } else if (topic.includes("alert")) {
            addLog(p.msg, "alert");
            dom.disp.alert.innerText = p.msg;
            dom.disp.alert.className = "text-sm text-red-400 mt-2 font-bold animate-pulse";
        }
    } catch (e) { console.error(e); }
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
        payload.temp_ext = inputState.text; 
        payload.carga = inputState.load; 
        addLog("A iniciar simulação...");
    }
    
    const message = new Paho.MQTT.Message(JSON.stringify(payload));
    message.destinationName = "datacenter/fuzzy/cmd";
    client.send(message);
}

function generatePDF() {
    const doc = new jsPDF();
    doc.setFontSize(18);
    doc.text("Relatório de Controlo Fuzzy", 14, 20);
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
    onSuccess: () => {
        document.getElementById('status-badge').innerHTML = '<div class="w-2 h-2 rounded-full bg-green-500"></div> ON';
        addLog("Conectado ao Broker!", "success");
        client.subscribe("datacenter/fuzzy/#");
    },
    onFailure: (e) => {
        addLog("Falha na conexão: " + e.errorMessage, "alert");
    }
});