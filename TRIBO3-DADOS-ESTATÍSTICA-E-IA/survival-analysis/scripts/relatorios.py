"""Pendências e cards da rodada; não emite parecer de gate."""
from .registro import NOTA_USO, VERSAO_MODELO


def verificar_pendencias(meta, avaliacao, padrao):
    motivos = []
    if meta.get('fonte') != 'banco':
        motivos.append('Fonte não oficial: fixture não encerra o Passo 2.')
    if meta.get('n_excluidos', 0):
        motivos.append(f"{meta['n_excluidos']} registro(s) excluído(s) com motivo; conferir a auditoria, sem reinseri-los automaticamente.")
    exposicao = meta.get('exposicao', {})
    if exposicao.get('n_sem_exposicao', 1) or exposicao.get('n_diferencas_acima_003_anos', 1):
        motivos.append('Revisar ausência/divergência de exposição com o Passo 1.')
    for nome in ['Cox PH', 'Random Survival Forest']:
        met = avaliacao.get('modelos', {}).get(nome, {})
        nomes_metricas = {'c_index': 'C-index', 'brier': 'Brier', 'ibs': 'IBS',
                          'erro_calibracao_global': 'erro de calibração global'}
        ausentes = [rotulo for chave, rotulo in nomes_metricas.items() if met.get(chave) is None]
        if ausentes:
            motivos.append(f"{nome}: métricas indisponíveis: {', '.join(ausentes)}; conferir os motivos em avaliacao/resultado.json.")
    grupos = avaliacao.get('subgrupos', [])
    limitados = sum(row.get('c_index') is None or row.get('erro_calibracao_global') is None for row in grupos)
    if not grupos:
        motivos.append('Validação por subgrupo não produziu estimativas: ajuste indisponível.')
    elif limitados:
        motivos.append(f'Validação por subgrupo executada; {limitados}/{len(grupos)} avaliações sem suporte estatístico suficiente (motivos registrados).')
    if avaliacao.get('dependencia_covariaveis', {}).get('alertas'):
        motivos.append('Correlação alta no treino: justificar manutenção/alteração das covariáveis.')
    ph = avaliacao.get('schoenfeld_treino_p')
    if ph is None or any(v is None or v < .05 for v in ph.values()):
        motivos.append('Schoenfeld indisponível ou sinaliza violação: revisar hipótese PH.')
    if not padrao.get('recupera_direcoes'):
        motivos.append('Padrão idade/sexo divergente ou inconclusivo; não alterar seed para forçar aprovação.')
    if avaliacao.get('veredito', {}).get('status') == 'inconclusivo':
        motivos.append('Comparação champion/challenger inconclusiva; baseline permanece sem superioridade declarada.')
    return motivos


def criterios_issue34(avaliacao):
    """Distingue critério executado de evidência estatística indisponível.

    Não é aceite humano nem gate: um diagnóstico inconclusivo é documentado,
    não apagado e não convertido em validação científica positiva.
    """
    modelos = avaliacao.get('modelos', {})
    metricas = bool(modelos) and all(m.get(k) is not None for m in modelos.values()
        for k in ['c_index', 'brier', 'ibs', 'erro_calibracao_global'])
    artefatos = avaliacao.get('artefatos_modelos', {})
    estimativas = bool(artefatos) and all('calibracao' in modelos.get(nome, {}) for nome in artefatos)
    grupos = avaliacao.get('subgrupos', [])
    suporte = bool(grupos) and all(r.get('c_index') is not None and
        r.get('erro_calibracao_global') is not None for r in grupos)
    dependencia = bool(avaliacao.get('dependencia_covariaveis', {}).get('decisoes'))
    return [
        dict(criterio='Estimativas de sobrevivência (RF02/RF05)', status='executado' if estimativas else 'sem_suporte',
             evidencia='avaliacao/modelos/estimativas_teste.csv'),
        dict(criterio='Calibração e discriminação (RF04)', status='executado' if metricas else 'sem_suporte',
             evidencia='avaliacao/resultado.json'),
        dict(criterio='Validação temporal e por subgrupo', status=(
             'executado' if suporte else 'executado_com_limitacoes' if grupos else 'sem_suporte'),
             evidencia='avaliacao/divisao_temporal.csv; avaliacao/metricas_subgrupos.csv'),
        dict(criterio='Correlação/dependência (RF03)', status='executado' if dependencia else 'nao_executado',
             evidencia='avaliacao/dependencia_covariaveis.json'),
        dict(criterio='Model card e experiment record', status='gerados_na_rodada',
             evidencia='model_card.md; experiment_record.md; versionamento no registro do módulo'),
    ]


def escrever_cards(out, meta, avaliacao, padrao, fechamento):
    """Cards da rodada, sem substituir o histórico dos documentos do módulo."""
    linhas = []
    for nome, met in avaliacao['modelos'].items():
        linhas.append('| ' + ' | '.join(str(x) for x in [nome,
            met.get('c_index'), met.get('brier'), met.get('ibs'),
            met.get('erro_calibracao_global')]) + ' |')
    padroes = '\n'.join('| ' + ' | '.join(str(x) for x in [v['modelo'], v['fator'],
        v.get('hr', v.get('diferenca_prob_obito')), v['status']]) + ' |'
        for v in padrao.get('verificacoes', []))
    criterios = '\n'.join('| ' + ' | '.join([c['criterio'], c['status'], c['evidencia']]) + ' |'
        for c in fechamento.get('criterios_issue34', []))
    comum = f"""Versão do modelo: {VERSAO_MODELO}. Referência: {meta['data_referencia']}.
Fonte declarada: {meta.get('fonte', 'não informada')}; identificação declarada: {meta['identificacao_fonte']}.
Extração do Postgres não comprova, por si só, a calibração/versão da carga.
SHA-256 do dataset: `{meta['dataset_sha256']}`.
Registros brutos/analíticos/excluídos/óbitos: {meta['n_bruto']} / {meta['n_analitico']} / {meta['n_excluidos']} / {meta['n_obitos']}.
Corte: {avaliacao['data_corte']}; horizonte: {avaliacao['horizonte_anos']} anos.
Treino/teste: {avaliacao['n_treino']} / {avaliacao['n_teste']};
óbitos treino/teste: {avaliacao['eventos_treino']} / {avaliacao['eventos_teste']}.

| Modelo | C-index teste | Brier | IBS | Erro calibração global |
|---|---|---|---|---|
{chr(10).join(linhas)}

| Diagnóstico | Fator | HR Cox ou diferença de P(óbito) KM | Direção |
|---|---|---|---|
{padroes}

Modelo mantido: {avaliacao['veredito']['modelo_mantido']}.
Comparação: {avaliacao['veredito']['status']} — {avaliacao['veredito']['motivo']}.
Verificação técnica: {fechamento['status']}.

| Critério da issue #34 | Execução | Evidência |
|---|---|---|
{criterios}

Esta tabela registra a execução dos critérios; não representa aceite ou aprovação de gate.

**{NOTA_USO}**
"""
    pendencias = '\n'.join(f'- {p}' for p in fechamento['pendencias']) or '- Nenhuma pendência técnica automática.'
    (out/'model_card.md').write_text(f"""# Model card — rodada do Passo 2

{comum}
## Método e uso

KM descritivo; Cox PH (ridge 0,01), baseline interpretável; RSF (100 árvores,
split 10, leaf 5, max_features sqrt), challenger. Covariáveis e hiperparâmetros
estão em `avaliacao/resultado.json`. Referências: F, CV e Plano C.
Calibração: média prevista versus 1−KM, com IC95%; Brier/IBS usam IPCW do treino.
Discriminação: C-index. Teste por calendário, censurando desfechos de treino no corte.
Dependência avaliada somente no treino: Pearson, Spearman e Cramér V.
Decisões por covariável e justificativa de não usar cópulas: `avaliacao/dependencia_covariaveis.json`.

## Limitações e revisão

{pendencias}

O gerador versionado do Passo 1 declara mortalidade IBGE 2024 (seleção 0,85),
mas o manifesto desta extração não prova que essa versão gerou a carga consultada.
Não atribuir automaticamente essas premissas ao lote. Dados sintéticos não
demonstram validade externa; a origem dos demais decrementos exige o data card da carga.
KM por idade ao ingresso e sexo é marginal, sujeito a composição da massa.
Direção pontual não implica significância nem estima o qx original com exatidão.
O cadastro é atual: este desenho não reconstrói o conhecimento bitemporal histórico.
Poucos eventos tornam métricas por subgrupo inconclusivas; censura independente
é uma hipótese. Calibração global pode ocultar erros individuais.
Revisão humana da dupla e gate T6 permanecem necessários.
Autores responsáveis: Caio Brandão Santos e Pedro Lucas Figueiredo Santana.
""", encoding='utf-8')
    (out/'experiment_record.md').write_text(f"""# Experiment record — rodada do Passo 2

Emissão UTC: {fechamento['executado_em']}.
{comum}
## Evidências reproduzíveis

- `fechamento.json`: pendências; não é parecer de gate T6.
- `dataset_survival.metadata.json`: procedência, referência, contagens e hashes.
- `avaliacao/resultado.json`: métricas, hiperparâmetros, bootstrap e ambiente.
- `avaliacao/divisao_temporal.csv`: censura de treino e composição do holdout.
- `avaliacao/metricas_subgrupos.csv` e `calibracao.csv`: suporte, IC e motivos.
- `avaliacao/correlacao_pearson.csv`, `correlacao_spearman.csv`,
  `decisoes_covariaveis.csv` e `dependencia_covariaveis.json`: decisões no treino.
- `padrao_mortalidade.json`: KM e HR Cox para idade/sexo, inclusive IC e divergências.
- `avaliacao/modelos/`: modelos ajustados no treino e estimativas do teste.
- `manifesto_artefatos.json`: integridade das saídas para os Passos 7/8.

## Pendências

{pendencias}

Não escolher seed, corte ou horizonte para melhorar o resultado. Preservar esta
rodada e registrar qualquer nova especificação com justificativa anterior à avaliação.
Antes do fechamento, conferir o lote/calibração com o Passo 1, revisar estes cards
e comunicar manualmente a dupla 7/8 com o manifesto e os modelos. Carregar joblib
somente de artefato produzido/conferido pela equipe (desserialização executa código).
IDs sintéticos e datas ficam na pasta de execução; não publicar microdados reais.
""", encoding='utf-8')
