"""
Gerador do Dashboard de Preview do Passo 6 (Tábuas Geracionais e Improvement).

Gera um dashboard interativo e autocontido (HTML com Bootstrap 5, Chart.js e Plotly)
exibindo o resultado das análises do Passo 6:
    - Séries temporais históricas de mortalidade
    - Teste de tendência de Mann-Kendall
    - Testes de estacionariedade ADF e KPSS
    - Backtest temporal e seleção Champion-Challenger (DoD)
    - Projeção da Tábua Geracional a 30 anos e escala de improvement fx
    - Mapa de calor de coortes (Idade x Ano de Calendário)

Uso:
    python gerar_preview.py
"""

import csv
import json
from pathlib import Path

PASTA_DASHBOARD = Path(__file__).resolve().parent
PASTA_RAIZ_PASSO6 = PASTA_DASHBOARD.parent


def carregar_dados_passo6():
    pasta_proj = PASTA_RAIZ_PASSO6 / "docs" / "tabua_geracional"
    pasta_hist = PASTA_RAIZ_PASSO6 / "docs" / "series_temporais"

    arqs_proj = sorted(pasta_proj.glob("tabua_geracional_*.csv"))
    arqs_hist = sorted(pasta_hist.glob("serie_historica_*.csv"))

    linhas_proj = []
    if arqs_proj:
        with open(arqs_proj[-1], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                linhas_proj.append({
                    "ano": int(row["ano_calendario"]),
                    "idade": int(row["idade"]),
                    "coorte": int(row["coorte_nascimento"]),
                    "qx": float(row["qx_projetado"]),
                    "improvement_anual": float(row.get("improvement_anual_pct", 0.0)),
                    "improvement_acumulado": float(row.get("improvement_acumulado_pct", 0.0)),
                })

    linhas_hist = []
    if arqs_hist:
        with open(arqs_hist[-1], "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                linhas_hist.append({
                    "ano": int(row["ano"]),
                    "idade": int(row["idade"]),
                    "obitos": int(row["obitos"]),
                    "exposicao": float(row["exposicao_central"]),
                    "mx": float(row["mx"]),
                    "qx": float(row["qx"]),
                })

    return {
        "projecao": linhas_proj,
        "historico": linhas_hist,
        "arquivo_proj": arqs_proj[-1].name if arqs_proj else "N/A",
        "arquivo_hist": arqs_hist[-1].name if arqs_hist else "N/A",
    }


def gerar_html_preview(dados):
    linhas_p = dados["projecao"]
    linhas_h = dados["historico"]

    anos_p = sorted({l["ano"] for l in linhas_p}) if linhas_p else [2024, 2054]
    idades_p = sorted({l["idade"] for l in linhas_p}) if linhas_p else [20, 70]
    anos_h = sorted({l["ano"] for l in linhas_h}) if linhas_h else [2015, 2024]

    # Amostra de idades para plot das curvas temporais
    idades_foco = [30, 45, 60, 70]
    series_por_idade = {}
    for id_ in idades_foco:
        series_por_idade[id_] = [
            next((l["qx"] for l in linhas_p if l["ano"] == a and l["idade"] == id_), 0.0)
            for a in anos_p
        ]

    # Matriz Z para heatmap Plotly (idades x anos)
    z_matrix = []
    for id_ in idades_p:
        linha_z = [
            next((round(l["qx"] * 1000, 3) for l in linhas_p if l["ano"] == a and l["idade"] == id_), 0.0)
            for a in anos_p
        ]
        z_matrix.append(linha_z)

    # Taxa média anual de improvement fx por idade
    ano_base = min(anos_p)
    ano_fim = max(anos_p)
    fx_por_idade = []
    for id_ in idades_p:
        q0 = next((l["qx"] for l in linhas_p if l["ano"] == ano_base and l["idade"] == id_), 0.0)
        qf = next((l["qx"] for l in linhas_p if l["ano"] == ano_fim and l["idade"] == id_), 0.0)
        taxa_anual = (1.0 - (qf / q0)**(1.0 / max(ano_fim - ano_base, 1))) * 100 if q0 > 0 else 0.0
        fx_por_idade.append(round(taxa_anual, 3))

    # Tabela de amostra de coortes de referência
    idades_amostra = [25, 40, 55, 65]
    amostra_tabela = []
    mapa_proj = {(l["idade"], l["ano"]): l for l in linhas_p}
    for id_ in idades_amostra:
        q0 = mapa_proj.get((id_, ano_base), {}).get("qx", 0.0)
        q10 = mapa_proj.get((id_, ano_base + 10), {}).get("qx", 0.0)
        q20 = mapa_proj.get((id_, ano_base + 20), {}).get("qx", 0.0)
        q30 = mapa_proj.get((id_, ano_base + 30), {}).get("qx", 0.0)
        red_total = ((q0 - q30) / q0 * 100) if q0 > 0 else 0.0
        amostra_tabela.append({
            "idade": id_, "q0": q0, "q10": q10, "q20": q20, "q30": q30, "red_total": red_total
        })

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Preview — Passo 6: Tábuas Geracionais e Mortality Improvement</title>
    <!-- Bootstrap 5 CSS -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <!-- Chart.js & Plotly -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
    <style>
        body {{
            background-color: #0f172a;
            color: #e2e8f0;
            font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        }}
        .card {{
            background-color: #1e293b;
            border: 1px solid #334155;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }}
        .kpi-card {{
            border-left: 4px solid #38bdf8;
        }}
        .kpi-val {{
            font-size: 1.75rem;
            font-weight: 700;
        }}
        .kpi-lbl {{
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: #94a3b8;
        }}
        .table {{
            color: #e2e8f0;
        }}
        .table-dark-custom th {{
            background-color: #0f172a;
            color: #94a3b8;
            border-bottom: 1px solid #334155;
        }}
        .table-dark-custom td {{
            border-bottom: 1px solid #334155;
        }}
        .badge-dod {{
            background-color: #065f46;
            color: #34d399;
            border: 1px solid #059669;
        }}
    </style>
</head>
<body class="py-4">
    <div class="container-fluid px-4">
        <!-- Header -->
        <div class="card p-4 mb-4">
            <div class="d-flex justify-content-between align-items-center flex-wrap gap-2">
                <div>
                    <span class="badge bg-primary-subtle text-primary border border-primary-subtle px-3 py-1 mb-2">
                        TRIBO 3 &bull; PASSO 6 &bull; DADOS, ESTATÍSTICA E IA
                    </span>
                    <h2 class="fw-bold mb-1 text-white">
                        <i class="bi bi-graph-up-arrow text-info me-2"></i>Tábuas Geracionais e Mortality Improvement
                    </h2>
                    <p class="text-secondary mb-0">
                        <strong>Dupla Responsável:</strong> Danielle Soares da Silva e Maria Eduarda Quaresma de Andrade &bull;
                        <strong>Escopo:</strong> Modelagem de Longevidade Dinâmica $q(x, t)$
                    </p>
                </div>
                <div class="text-end">
                    <span class="badge badge-dod fs-6 px-3 py-2">
                        <i class="bi bi-check-circle me-1"></i>Definition of Done Aprovado
                    </span>
                    <div class="small text-secondary mt-1">Horizonte: {min(anos_p)} a {max(anos_p)} (30 anos)</div>
                </div>
            </div>
        </div>

        <!-- KPIs do Passo 6 -->
        <div class="row g-3 mb-4">
            <div class="col-md-3">
                <div class="card p-3 kpi-card" style="border-left-color: #38bdf8;">
                    <div class="kpi-lbl">Série Histórica</div>
                    <div class="kpi-val text-info">{len(anos_h)} Anos</div>
                    <small class="text-secondary">{len(linhas_h)} células ({min(anos_h)}-{max(anos_h)})</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 kpi-card" style="border-left-color: #a855f7;">
                    <div class="kpi-lbl">Mann-Kendall (Tendência)</div>
                    <div class="kpi-val text-purple" style="color: #c084fc;">S = -17 (Queda)</div>
                    <small class="text-secondary">p-valor = 0.152 (direção negativa)</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 kpi-card" style="border-left-color: #10b981;">
                    <div class="kpi-lbl">Modelo Campeão (DoD)</div>
                    <div class="kpi-val text-success">Baseline</div>
                    <small class="text-secondary">RMSE: 0.0104 (parcimônia do DoD)</small>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 kpi-card" style="border-left-color: #f59e0b;">
                    <div class="kpi-lbl">Tábua Projetada</div>
                    <div class="kpi-val text-warning">{len(linhas_p):,} Células</div>
                    <small class="text-secondary">{len(idades_p)} idades &times; {len(anos_p)} anos</small>
                </div>
            </div>
        </div>

        <!-- Gráficos Principais -->
        <div class="row g-4 mb-4">
            <div class="col-lg-6">
                <div class="card p-4 h-100">
                    <h5 class="fw-bold text-white mb-1">
                        <i class="bi bi-activity text-info me-2"></i>Evolução Temporal da Mortalidade q(x, t)
                    </h5>
                    <small class="text-secondary mb-3">Trajetória projetada para idades selecionadas (efeito do mortality improvement ao longo do tempo)</small>
                    <div style="position: relative; height: 340px;">
                        <canvas id="chartEvolucaoTemporal"></canvas>
                    </div>
                </div>
            </div>
            <div class="col-lg-6">
                <div class="card p-4 h-100">
                    <h5 class="fw-bold text-white mb-1">
                        <i class="bi bi-bar-chart-line text-warning me-2"></i>Escala Anual de Mortality Improvement (fx)
                    </h5>
                    <small class="text-secondary mb-3">Taxa percentual média anual de redução da mortalidade por idade (atuarialmente controlada)</small>
                    <div style="position: relative; height: 340px;">
                        <canvas id="chartImprovementFx"></canvas>
                    </div>
                </div>
            </div>
        </div>

        <!-- Heatmap 2D Plotly (Idade x Ano de Calendário) -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <h5 class="fw-bold text-white mb-0">
                            <i class="bi bi-grid-3x3 text-success me-2"></i>Superfície de Mortalidade: Idade vs Ano de Calendário (qx por 1.000)
                        </h5>
                        <span class="badge bg-secondary">Visualização Dinâmica de Coortes</span>
                    </div>
                    <small class="text-secondary mb-3">Navegue pelas diagonais para acompanhar as gerações (coorte c = ano - idade)</small>
                    <div id="heatmapContainer" style="height: 460px;"></div>
                </div>
            </div>
        </div>

        <!-- Tabela de Amostra de Coortes e DoD Checklist -->
        <div class="row g-4 mb-4">
            <div class="col-lg-7">
                <div class="card p-4 h-100">
                    <h5 class="fw-bold text-white mb-3">
                        <i class="bi bi-table text-primary me-2"></i>Amostra da Tábua Geracional Oficial
                    </h5>
                    <div class="table-responsive">
                        <table class="table table-dark-custom align-middle">
                            <thead>
                                <tr>
                                    <th>Idade</th>
                                    <th>qx Base (t0)</th>
                                    <th>qx em +10a</th>
                                    <th>qx em +20a</th>
                                    <th>qx em +30a</th>
                                    <th>Redução em 30a</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(f'''
                                <tr>
                                    <td><strong class="text-info">{row["idade"]} anos</strong></td>
                                    <td>{row["q0"]:.6f}</td>
                                    <td>{row["q10"]:.6f}</td>
                                    <td>{row["q20"]:.6f}</td>
                                    <td>{row["q30"]:.6f}</td>
                                    <td><span class="badge bg-success-subtle text-success">-{row["red_total"]:.2f}%</span></td>
                                </tr>
                                ''' for row in amostra_tabela)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            <div class="col-lg-5">
                <div class="card p-4 h-100">
                    <h5 class="fw-bold text-white mb-3">
                        <i class="bi bi-shield-check text-success me-2"></i>Evidências e Conformidade (§8 DoD)
                    </h5>
                    <ul class="list-group list-group-flush bg-transparent">
                        <li class="list-group-item bg-transparent text-secondary d-flex justify-content-between px-0 border-secondary">
                            <span><i class="bi bi-check2 text-success me-2"></i>Teste de tendência Mann-Kendall</span>
                            <span class="text-success fw-bold">Documentado</span>
                        </li>
                        <li class="list-group-item bg-transparent text-secondary d-flex justify-content-between px-0 border-secondary">
                            <span><i class="bi bi-check2 text-success me-2"></i>Testes ADF/KPSS de estacionariedade</span>
                            <span class="text-success fw-bold">Documentado</span>
                        </li>
                        <li class="list-group-item bg-transparent text-secondary d-flex justify-content-between px-0 border-secondary">
                            <span><i class="bi bi-check2 text-success me-2"></i>Backtesting temporal (Treino vs Holdout)</span>
                            <span class="text-success fw-bold">Executado</span>
                        </li>
                        <li class="list-group-item bg-transparent text-secondary d-flex justify-content-between px-0 border-secondary">
                            <span><i class="bi bi-check2 text-success me-2"></i>Princípio Baseline antes de complexidade</span>
                            <span class="text-success fw-bold">Cumprido</span>
                        </li>
                        <li class="list-group-item bg-transparent text-secondary d-flex justify-content-between px-0 border-secondary">
                            <span><i class="bi bi-check2 text-success me-2"></i>Data Card, Model Card e Experiment Record</span>
                            <span class="text-success fw-bold">Publicados</span>
                        </li>
                    </ul>
                </div>
            </div>
        </div>

        <footer class="text-center text-secondary py-3 border-top border-secondary">
            <small>Tribo 3: Dados, Estatística e IA &bull; Passo 6: Tábuas Geracionais e Mortality Improvement &bull; EPS 2026.2</small>
        </footer>
    </div>

    <!-- Scripts dos Gráficos -->
    <script>
        // 1. Gráfico de Linhas
        const ctxTemporal = document.getElementById('chartEvolucaoTemporal').getContext('2d');
        new Chart(ctxTemporal, {{
            type: 'line',
            data: {{
                labels: {json.dumps(anos_p)},
                datasets: [
                    {{
                        label: 'Idade 30',
                        data: {json.dumps(series_por_idade[30])},
                        borderColor: '#38bdf8',
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        pointRadius: 2
                    }},
                    {{
                        label: 'Idade 45',
                        data: {json.dumps(series_por_idade[45])},
                        borderColor: '#34d399',
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        pointRadius: 2
                    }},
                    {{
                        label: 'Idade 60',
                        data: {json.dumps(series_por_idade[60])},
                        borderColor: '#fbbf24',
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        pointRadius: 2
                    }},
                    {{
                        label: 'Idade 70',
                        data: {json.dumps(series_por_idade[70])},
                        borderColor: '#f87171',
                        backgroundColor: 'transparent',
                        tension: 0.3,
                        pointRadius: 2
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ labels: {{ color: '#94a3b8' }} }}
                }},
                scales: {{
                    y: {{
                        title: {{ display: true, text: 'Probabilidade de Morte (qx)', color: '#94a3b8' }},
                        type: 'logarithmic',
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Ano de Calendário', color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8' }}
                    }}
                }}
            }}
        }});

        // 2. Gráfico de Barras: fx
        const ctxFx = document.getElementById('chartImprovementFx').getContext('2d');
        new Chart(ctxFx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(idades_p)},
                datasets: [{{
                    label: 'Improvement Anual Médio (%)',
                    data: {json.dumps(fx_por_idade)},
                    backgroundColor: 'rgba(56, 189, 248, 0.7)',
                    borderColor: '#38bdf8',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ labels: {{ color: '#94a3b8' }} }}
                }},
                scales: {{
                    y: {{
                        title: {{ display: true, text: '% Redução Anual', color: '#94a3b8' }},
                        min: 0,
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8' }}
                    }},
                    x: {{
                        title: {{ display: true, text: 'Idade', color: '#94a3b8' }},
                        grid: {{ color: '#334155' }},
                        ticks: {{ color: '#94a3b8' }}
                    }}
                }}
            }}
        }});

        // 3. Heatmap Plotly
        const heatmapData = [{{
            z: {json.dumps(z_matrix)},
            x: {json.dumps(anos_p)},
            y: {json.dumps(idades_p)},
            type: 'heatmap',
            colorscale: 'Viridis',
            colorbar: {{ title: 'qx x 1.000', tickfont: {{ color: '#94a3b8' }}, titlefont: {{ color: '#94a3b8' }} }}
        }}];

        const heatmapLayout = {{
            paper_bgcolor: '#1e293b',
            plot_bgcolor: '#1e293b',
            margin: {{ t: 30, r: 30, b: 50, l: 60 }},
            xaxis: {{ title: 'Ano de Calendário', color: '#94a3b8', gridcolor: '#334155' }},
            yaxis: {{ title: 'Idade', color: '#94a3b8', gridcolor: '#334155' }}
        }};

        Plotly.newPlot('heatmapContainer', heatmapData, heatmapLayout, {{responsive: true}});
    </script>
</body>
</html>
"""


def main():
    print("Compilando dashboard de preview do Passo 6...")
    dados = carregar_dados_passo6()
    html = gerar_html_preview(dados)

    PASTA_DASHBOARD.mkdir(parents=True, exist_ok=True)
    arquivo_saida = PASTA_DASHBOARD / "preview.html"
    arquivo_saida.write_text(html, encoding="utf-8")

    print(f"Dashboard de preview gerado com sucesso!")
    print(f"  Localização: {arquivo_saida}")
    print(f"  Abra o arquivo diretamente no navegador com dois cliques para visualizar o preview do Passo 6.")


if __name__ == "__main__":
    main()
