# Projeto-C213

Desenvolvido por Lara Conte Gomes e Lívia Cecília Gomes Silva

## Descrição do Projeto
O Projeto-C213 é uma aplicação que combina um backend desenvolvido em Python e um frontend em HTML, CSS e JavaScript. O objetivo do projeto é demonstrar o uso de lógica fuzzy para resolver problemas de classificação e tomada de decisão.

## Estrutura do Projeto
- **backend/**: Contém o código do servidor backend, incluindo a lógica fuzzy implementada em Python.
  - `main.py`: Arquivo principal do backend.
  - `requirements.txt`: Lista de dependências necessárias para o backend.
- **frontend/**: Contém os arquivos do frontend.
  - `index.html`: Página principal da aplicação.
  - `style.css`: Estilos da aplicação.
  - `app.js`: Lógica de interação do frontend.
- **Scripts/**: Scripts auxiliares para o projeto.
- **Projeto_C213.ipynb**: Notebook Jupyter com análises e experimentos relacionados ao projeto.
- **fuzzy.py**: Implementação da lógica fuzzy.

## Como Executar
### Pré-requisitos
- Python 3.9 ou superior
- Node.js (opcional, caso precise de ferramentas adicionais para o frontend)

### Passos para execução
1. Clone o repositório:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   ```
2. Navegue até a pasta do backend e instale as dependências:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```
3. Execute o servidor backend:
   ```bash
   python main.py
   ```
4. Abra o arquivo `index.html` no navegador para acessar o frontend.

## Tecnologias Utilizadas
- **Python**: Para o desenvolvimento do backend e lógica fuzzy.
- **HTML, CSS e JavaScript**: Para o desenvolvimento do frontend.

## Autores
- Lara Conte Gomes
- Lívia Cecília Gomes Silva

## Licença
Este projeto é distribuído sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## Detalhes da Lógica Fuzzy

A lógica fuzzy implementada no projeto é utilizada para controlar a potência do sistema de refrigeração (CRAC) em um data center. Abaixo estão os principais componentes e funcionamento:

### Variáveis de Entrada
1. **Erro de Temperatura (`erro`)**: Diferença entre a temperatura atual e a desejada (-12°C a +12°C).
2. **Variação do Erro (`delta_erro`)**: Taxa de mudança do erro (-2°C/min a +2°C/min).

### Variável de Saída
- **Potência do CRAC (`p_crac`)**: Percentual de potência do sistema de refrigeração (0% a 100%).

### Regras Fuzzy
As regras fuzzy definem como as variáveis de entrada influenciam a saída. Exemplos de regras:
- Se o erro for **muito negativo** e a variação do erro for **muito negativa**, então a potência deve ser **muito baixa**.
- Se o erro for **zero** e a variação do erro for **positiva**, então a potência deve ser **alta**.
- Se o erro for **muito positivo**, então a potência deve ser **máxima**.

### Funcionamento
1. **Definição de Funções de Pertinência**: Cada variável é representada por funções de pertinência (e.g., triangular, trapezoidal) que definem os graus de associação a categorias como "muito frio" ou "muito quente".
2. **Inferência Fuzzy**: As regras são avaliadas para determinar a potência necessária com base nas entradas.
3. **Defuzzificação**: O resultado fuzzy é convertido em um valor numérico para ajustar a potência do CRAC.

### Modelo Físico
O projeto também inclui um modelo físico simplificado para simular a dinâmica térmica do data center:
- **Fórmula**: T[n+1] = 0.9 * T[n] - 0.08 * P_CRAC + 0.05 * Q_est + 0.02 * T_ext + 3.5
- Onde:
  - T[n]: Temperatura atual
  - P_CRAC: Potência do CRAC
  - Q_est: Carga térmica
  - T_ext: Temperatura externa

Essa abordagem permite um controle eficiente e adaptativo da temperatura, garantindo o funcionamento ideal do data center.
