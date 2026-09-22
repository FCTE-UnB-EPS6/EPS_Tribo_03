"""Integração real: definir ESG_TEST_DATABASE_URL apontando para banco *_test."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Barrier
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4
from app.services.scenario_generator import loads_decimal, dumps_decimal, ScenarioError

ROOT = Path(__file__).resolve().parents[1]
DSN = os.environ.get('ESG_TEST_DATABASE_URL')


@unittest.skipUnless(DSN, 'Defina ESG_TEST_DATABASE_URL para testar PostgreSQL real.')
class PersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg
        from app.repositories.scenario_repository import ScenarioRepository
        from app.services.scenario_application import ScenarioApplication, RulesCatalog
        cls.psycopg = psycopg
        cls.repo = ScenarioRepository(DSN)
        with cls.repo.connect() as conn:
            if not conn.info.dbname.endswith('_test'):
                raise RuntimeError('Testes exigem banco dedicado com nome terminado em _test.')
        cls.repo.initialize()
        cls.application = ScenarioApplication(cls.repo, RulesCatalog([ROOT/'config/scenario_rules.demo.v0.1.0.json']))

    def setUp(self):
        with self.repo.connect() as conn:
            conn.execute('TRUNCATE economic_scenarios.scenario, economic_scenarios.run, economic_scenarios.assumption_set, economic_scenarios.trajectory_set, economic_scenarios.ruleset')
        self.request = loads_decimal((ROOT/'examples/generate.demo.v0.1.0.json').read_text())

    def counts(self):
        with self.repo.connect() as conn:
            return tuple(conn.execute('SELECT count(*) FROM economic_scenarios.' + table).fetchone()[0]
                         for table in ('assumption_set','ruleset','run','scenario'))

    def trajectory_count(self):
        with self.repo.connect() as conn:
            return conn.execute(
                'SELECT count(*) FROM economic_scenarios.trajectory_set'
            ).fetchone()[0]

    def test_roundtrip_and_new_repository(self):
        from app.repositories.scenario_repository import ScenarioRepository
        result = self.application.generate(self.request)
        UUID(result['run_id'])
        self.assertTrue(result['created_at'].endswith('Z'))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(ScenarioRepository(DSN).get_run(result['run_id']), result)
        for scenario in result['scenarios']:
            UUID(scenario['scenario_id'])
            self.assertEqual(self.application.get_scenario(scenario['scenario_id']),
                             {'run_id':result['run_id'], 'scenario':scenario})
        self.assertEqual(self.counts(), (1,1,1,3))

    def test_repeated_generation_and_numeric_equivalence(self):
        first = self.application.generate(self.request)
        self.request['assumptions']['inflation']=Decimal('0.040000000000')
        self.request['assumptions'] = dict(reversed(list(self.request['assumptions'].items())))
        second = self.application.generate(self.request)
        self.assertNotEqual(first['run_id'],second['run_id'])
        self.assertEqual(first['scenarios'][0]['values'],second['scenarios'][0]['values'])
        self.assertEqual(self.counts(),(1,1,2,6))

    def test_date_and_horizon_not_part_of_assumption_identity(self):
        self.application.generate(self.request)
        self.request.update(base_date='2027-01-01',horizon_years=2)
        self.application.generate(self.request)
        self.assertEqual(self.counts(),(1,1,2,6))

    def test_assumption_and_source_conflicts(self):
        self.application.generate(self.request)
        original=deepcopy(self.request)
        for change_source in (False,True):
            self.request=deepcopy(original)
            if change_source:
                self.request['sources']['inflation']['description']='outra origem'
            else:
                self.request['assumptions']['inflation']=Decimal('0.05')
            with self.assertRaises(ScenarioError) as caught:
                self.application.generate(self.request)
            self.assertEqual(caught.exception.code,'ASSUMPTION_VERSION_CONFLICT')
            self.assertEqual(self.counts(),(1,1,1,3))

    def test_new_version_allowed(self):
        self.application.generate(self.request)
        self.request['assumption_version']='0.2.0'
        self.request['assumptions']['inflation']=Decimal('0.05')
        self.application.generate(self.request)
        self.assertEqual(self.counts(),(2,1,2,6))

    def test_trajectory_contract_roundtrip_and_version_conflict(self):
        from app.services.scenario_application import RulesCatalog, ScenarioApplication
        application = ScenarioApplication(
            self.repo,
            RulesCatalog([ROOT / 'config/scenario_rules.trajectory.v0.2.0.json']),
        )
        request = loads_decimal(
            (ROOT / 'examples/trajectory.demo.v0.2.0.json').read_text()
        )
        result = application.generate(request)
        self.assertEqual(result['contract_version'], '0.2.0')
        self.assertEqual(self.repo.get_run(result['run_id']), result)
        self.assertEqual(self.counts(), (0,1,1,3))
        self.assertEqual(self.trajectory_count(), 1)
        request['trajectory']['periods'][0]['variables']['inflation']['value'] = Decimal('0.05')
        with self.assertRaises(ScenarioError) as caught:
            application.generate(request)
        self.assertEqual(caught.exception.code, 'TRAJECTORY_VERSION_CONFLICT')
        self.assertEqual(self.counts(), (0,1,1,3))

    def test_rules_conflict_rolls_back_new_assumptions(self):
        from app.services.scenario_application import RulesCatalog,ScenarioApplication
        self.application.generate(self.request)
        rules=loads_decimal((ROOT/'config/scenario_rules.demo.v0.1.0.json').read_text())
        rules['scenarios']['adverse']['adjustments']['inflation']=Decimal('0.03')
        with TemporaryDirectory() as temp:
            path=Path(temp)/'rules.json'; path.write_text(dumps_decimal(rules))
            changed=ScenarioApplication(self.repo,RulesCatalog([path]))
            self.request['assumption_version']='0.2.0'
            with self.assertRaises(ScenarioError) as caught:
                changed.generate(self.request)
        self.assertEqual(caught.exception.code,'INVALID_RULESET')
        self.assertEqual(self.counts(),(1,1,1,3))

    def test_late_insert_failure_rolls_back_everything(self):
        with self.repo.connect() as conn:
            conn.execute("CREATE FUNCTION economic_scenarios.test_failure() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.scenario_key = 'favorable' THEN RAISE EXCEPTION 'test failure'; END IF; RETURN NEW; END; $$")
            conn.execute('CREATE TRIGGER test_failure BEFORE INSERT ON economic_scenarios.scenario FOR EACH ROW EXECUTE FUNCTION economic_scenarios.test_failure()')
        try:
            with self.assertRaises(ScenarioError) as caught:
                self.application.generate(self.request)
            self.assertEqual(caught.exception.code,'STORAGE_UNAVAILABLE')
            self.assertEqual(self.counts(),(0,0,0,0))
        finally:
            with self.repo.connect() as conn:
                conn.execute('DROP TRIGGER test_failure ON economic_scenarios.scenario')
                conn.execute('DROP FUNCTION economic_scenarios.test_failure()')

    def concurrent(self, conflicting):
        barrier=Barrier(2)
        def worker(index):
            request=deepcopy(self.request)
            if conflicting and index:
                request['assumptions']['inflation']=Decimal('0.05')
            barrier.wait(timeout=5)
            try:
                return self.application.generate(request)['run_id']
            except ScenarioError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(worker,range(2)))

    def test_concurrent_same_content(self):
        results=self.concurrent(False)
        for result in results: UUID(result)
        self.assertNotEqual(*results)
        self.assertEqual(self.counts(),(1,1,2,6))

    def test_concurrent_conflicting_content(self):
        results=self.concurrent(True)
        self.assertEqual(results.count('ASSUMPTION_VERSION_CONFLICT'),1)
        self.assertEqual(self.counts(),(1,1,1,3))

    def test_immutable_tables_and_idempotent_migration(self):
        from app.services.scenario_application import RulesCatalog, ScenarioApplication
        result=self.application.generate(self.request)
        trajectory_application = ScenarioApplication(
            self.repo,
            RulesCatalog([ROOT / 'config/scenario_rules.trajectory.v0.2.0.json']),
        )
        trajectory_application.generate(
            loads_decimal((ROOT / 'examples/trajectory.demo.v0.2.0.json').read_text())
        )
        self.repo.initialize()
        for table in ('run','scenario','assumption_set','trajectory_set','ruleset'):
            for sql in ('UPDATE economic_scenarios.'+table+' SET content=content',
                        'DELETE FROM economic_scenarios.'+table):
                with self.assertRaises(self.psycopg.Error):
                    with self.repo.connect() as conn: conn.execute(sql)
        self.assertEqual(self.application.get_run(result['run_id']),result)

    def test_not_found_invalid_uuid_and_unknown_rules(self):
        for method,code in ((self.application.get_run,'RUN_NOT_FOUND'),(self.application.get_scenario,'SCENARIO_NOT_FOUND')):
            with self.assertRaises(ScenarioError) as caught: method(str(uuid4()))
            self.assertEqual(caught.exception.code,code)
            with self.assertRaises(ScenarioError) as caught: method('invalid')
            self.assertEqual(caught.exception.code,'INVALID_REQUEST')
        self.request['ruleset_id']='../../etc/passwd'
        with self.assertRaises(ScenarioError) as caught: self.application.generate(self.request)
        self.assertEqual(caught.exception.code,'RULESET_NOT_FOUND')
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_unavailable_storage_has_no_credentials_in_error(self):
        with patch.object(self.repo,'connect',side_effect=self.psycopg.OperationalError('secret DSN')):
            with self.assertRaises(ScenarioError) as caught: self.application.generate(self.request)
        self.assertEqual(caught.exception.code,'STORAGE_UNAVAILABLE')
        self.assertNotIn('secret',str(caught.exception))
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_invalid_request_not_persisted(self):
        self.request['assumptions']['inflation']=-1
        with self.assertRaises(ScenarioError): self.application.generate(self.request)
        self.assertEqual(self.counts(),(0,0,0,0))

    def test_cli_generation_and_queries(self):
        env = {**os.environ, 'ESG_DATABASE_URL': DSN}
        def command(*args):
            return subprocess.run([sys.executable, '-m', 'app', *args], cwd=ROOT,
                                  env=env, text=True, capture_output=True, timeout=15)
        initialized = command('init-db')
        self.assertEqual(initialized.returncode, 0, initialized.stderr)
        generated = command('generate', 'examples/generate.demo.v0.1.0.json')
        self.assertEqual(generated.returncode, 0, generated.stderr)
        record = loads_decimal(generated.stdout)
        queried = command('get-run', record['run_id'])
        self.assertEqual(queried.returncode, 0, queried.stderr)
        self.assertEqual(loads_decimal(queried.stdout), record)
        queried = command('get-scenario', record['scenarios'][0]['scenario_id'])
        self.assertEqual(queried.returncode, 0, queried.stderr)
        self.assertEqual(loads_decimal(queried.stdout)['scenario'], record['scenarios'][0])
        bad = command('get-run', 'invalid')
        self.assertEqual(bad.returncode, 1)
        self.assertEqual(loads_decimal(bad.stderr)['error']['code'], 'INVALID_REQUEST')
