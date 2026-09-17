"""PostgreSQL: gravação atômica e proteção de versões sob concorrência."""
from pathlib import Path
import psycopg
from app.services.scenario_generator import dumps_decimal, loads_decimal, fail

MIGRATION = Path(__file__).resolve().parents[2] / 'migrations/001_execution_store.sql'


class ScenarioRepository:
    def __init__(self, dsn):
        self.dsn = dsn

    def connect(self):
        return psycopg.connect(self.dsn, connect_timeout=5)

    def initialize(self):
        """Aplicação explícita da migration; não executada a cada geração."""
        try:
            with self.connect() as conn:
                conn.execute(MIGRATION.read_text())
        except psycopg.Error:
            fail('STORAGE_UNAVAILABLE', None, 'Não foi possível inicializar o armazenamento.')

    def save(self, result):
        request, rules = result['request_snapshot'], result['ruleset_snapshot']
        assumption_content = {k: request[k] for k in ('unit', 'rate_basis', 'assumptions', 'sources')}
        try:
            # Um INSERT concorrente espera o vencedor; SELECT seguinte vê o commit
            # em READ COMMITTED. Conflitos abortam também os registros anteriores.
            with self.connect() as conn:
                conn.execute('INSERT INTO economic_scenarios.assumption_set VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING',
                             (request['assumption_set_id'], request['assumption_version'], dumps_decimal(assumption_content)))
                stored = conn.execute('SELECT content::text FROM economic_scenarios.assumption_set WHERE id=%s AND version=%s',
                                      (request['assumption_set_id'], request['assumption_version'])).fetchone()[0]
                if loads_decimal(stored) != assumption_content:
                    fail('ASSUMPTION_VERSION_CONFLICT', 'assumption_version', 'ID e versão já registrados com outras premissas ou fontes.')
                conn.execute('INSERT INTO economic_scenarios.ruleset VALUES (%s,%s,%s::jsonb) ON CONFLICT DO NOTHING',
                             (rules['ruleset_id'], rules['ruleset_version'], dumps_decimal(rules)))
                stored = conn.execute('SELECT content::text FROM economic_scenarios.ruleset WHERE id=%s AND version=%s',
                                      (rules['ruleset_id'], rules['ruleset_version'])).fetchone()[0]
                if loads_decimal(stored) != rules:
                    fail('INVALID_RULESET', 'ruleset_version', 'ID e versão de regras já registrados com outro conteúdo.')
                conn.execute('INSERT INTO economic_scenarios.run VALUES (%s,%s,%s,%s,%s,%s::jsonb)',
                             (result['run_id'], request['assumption_set_id'], request['assumption_version'],
                              rules['ruleset_id'], rules['ruleset_version'], dumps_decimal(result)))
                for scenario in result['scenarios']:
                    conn.execute('INSERT INTO economic_scenarios.scenario VALUES (%s,%s,%s,%s::jsonb)',
                                 (scenario['scenario_id'], result['run_id'], scenario['scenario_key'], dumps_decimal(scenario)))
        except psycopg.Error:
            fail('STORAGE_UNAVAILABLE', None, 'Não foi possível persistir a execução completa.')

    def get_run(self, run_id):
        try:
            with self.connect() as conn:
                row = conn.execute('SELECT content::text FROM economic_scenarios.run WHERE id=%s', (run_id,)).fetchone()
        except psycopg.Error:
            fail('STORAGE_UNAVAILABLE', None, 'Não foi possível consultar o armazenamento.')
        if row is None:
            fail('RUN_NOT_FOUND', 'run_id', 'Execução não encontrada.')
        return loads_decimal(row[0])

    def get_scenario(self, scenario_id):
        try:
            with self.connect() as conn:
                row = conn.execute('SELECT run_id::text, content::text FROM economic_scenarios.scenario WHERE id=%s', (scenario_id,)).fetchone()
        except psycopg.Error:
            fail('STORAGE_UNAVAILABLE', None, 'Não foi possível consultar o armazenamento.')
        if row is None:
            fail('SCENARIO_NOT_FOUND', 'scenario_id', 'Cenário não encontrado.')
        return {'run_id': row[0], 'scenario': loads_decimal(row[1])}
