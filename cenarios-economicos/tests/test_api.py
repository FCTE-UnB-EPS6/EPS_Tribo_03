"""Contrato HTTP e integração com banco descartável *_test."""
from decimal import Decimal
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4
from app.services.scenario_generator import ScenarioError, loads_decimal, dumps_decimal

ROOT=Path(__file__).resolve().parents[1]
AVAILABLE=all(importlib.util.find_spec(name) for name in ('fastapi','httpx','psycopg'))
DSN=os.environ.get('ESG_TEST_DATABASE_URL')


@unittest.skipUnless(AVAILABLE,'Instale requirements-dev.txt para testar HTTP.')
class HttpContractTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        self.application=Mock()
        self.client=TestClient(create_app(self.application),raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_health_without_storage(self):
        response=self.client.get('/health')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json(),{'status':'ok'})
        self.assertEqual(self.application.mock_calls,[])

    def test_invalid_json_utf8_duplicates_and_media_type(self):
        for body in (b'{',b'{"x":NaN}',b'{"x":Infinity}',b'{"x":1,"x":2}',b'\xff',b''):
            with self.subTest(body=body):
                response=self.client.post('/api/v1/scenarios/generate',content=body,headers={'Content-Type':'application/json'})
                self.assertEqual(response.status_code,400)
                self.assertEqual(response.json()['error']['code'],'INVALID_JSON')
        response=self.client.post('/api/v1/scenarios/generate',content='{}')
        self.assertEqual(response.status_code,415)
        self.application.generate.assert_not_called()

    def test_exact_decimal_parsing_and_response(self):
        self.application.generate.return_value={'run_id':str(uuid4()),'number':Decimal('0.12345678')}
        response=self.client.post('/api/v1/scenarios/generate',content='{"number":0.12345678}',headers={'Content-Type':'application/json; charset=utf-8'})
        self.assertEqual(response.status_code,201)
        self.assertEqual(self.application.generate.call_args.args[0]['number'],Decimal('0.12345678'))
        self.assertIn('"number":0.12345678',response.text)
        self.assertEqual(response.headers['location'],'/api/v1/runs/'+response.json()['run_id'])

    def test_domain_errors_status_and_envelope(self):
        from app.main import STATUS
        for code,status in STATUS.items():
            with self.subTest(code=code):
                self.application.generate.side_effect=ScenarioError(code,'field','mensagem')
                response=self.client.post('/api/v1/scenarios/generate',json={})
                self.assertEqual(response.status_code,status)
                self.assertEqual(response.json(),{'error':{'code':code,'field':'field','message':'mensagem'}})
                self.assertNotIn('location',response.headers)

    def test_internal_error_is_sanitized(self):
        self.application.generate.side_effect=RuntimeError('postgresql://secret:password@host/db')
        response=self.client.post('/api/v1/scenarios/generate',json={})
        self.assertEqual(response.status_code,500)
        self.assertEqual(response.json()['error']['code'],'INTERNAL_ERROR')
        self.assertNotIn('password',response.text)

    def test_router_errors(self):
        for method,path,status in [('get','/missing',404),('put','/health',405)]:
            response=getattr(self.client,method)(path)
            self.assertEqual(response.status_code,status)
            self.assertIn('error',response.json())
        self.assertIn('GET',self.client.put('/health').headers['allow'])

    def test_openapi_and_docs(self):
        document=self.client.get('/openapi.json').json()
        endpoint=document['paths']['/api/v1/scenarios/generate']['post']
        schema=endpoint['requestBody']['content']['application/json']['schema']
        self.assertFalse(schema['additionalProperties'])
        self.assertIn('sources',schema['required'])
        self.assertIn('request_snapshot',endpoint['responses']['201']['content']['application/json']['schema']['properties'])
        self.assertIn('Location',endpoint['responses']['201']['headers'])
        self.assertEqual(self.client.get('/docs').status_code,200)

    def test_factory_requires_connection_configuration(self):
        from app.main import create_app
        with patch.dict(os.environ,{},clear=True), self.assertRaises(RuntimeError):
            create_app()


@unittest.skipUnless(AVAILABLE and DSN,'Defina ESG_TEST_DATABASE_URL e instale requirements-dev.txt.')
class HttpPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from app.repositories.scenario_repository import ScenarioRepository
        cls.repo=ScenarioRepository(DSN)
        with cls.repo.connect() as conn:
            if not conn.info.dbname.endswith('_test'):
                raise RuntimeError('Banco dedicado deve terminar em _test.')
        cls.repo.initialize()

    def setUp(self):
        from fastapi.testclient import TestClient
        from app.main import create_app
        from app.services.scenario_application import ScenarioApplication,RulesCatalog
        with self.repo.connect() as conn:
            conn.execute('TRUNCATE economic_scenarios.scenario, economic_scenarios.run, economic_scenarios.assumption_set, economic_scenarios.ruleset')
        self.application=ScenarioApplication(self.repo,RulesCatalog([ROOT/'config/scenario_rules.demo.v0.1.0.json']))
        self.client=TestClient(create_app(self.application),raise_server_exceptions=False)
        self.addCleanup(self.client.close)
        self.request=loads_decimal((ROOT/'examples/generate.demo.v0.1.0.json').read_text())

    def post(self):
        return self.client.post('/api/v1/scenarios/generate',content=dumps_decimal(self.request),headers={'Content-Type':'application/json'})

    def test_generate_then_get_persisted_content(self):
        response=self.post()
        self.assertEqual(response.status_code,201,response.text)
        result=loads_decimal(response.text)
        self.assertEqual(result['status'],'completed')
        self.assertEqual(len(result['scenarios']),3)
        queried=self.client.get(response.headers['location'])
        self.assertEqual(queried.status_code,200)
        self.assertEqual(loads_decimal(queried.text),result)
        for scenario in result['scenarios']:
            queried=self.client.get('/api/v1/scenarios/'+scenario['scenario_id'])
            self.assertEqual(queried.status_code,200)
            self.assertEqual(loads_decimal(queried.text),{'run_id':result['run_id'],'scenario':scenario})
        self.assertEqual(self.repo.get_run(result['run_id']),result)

    def test_repeated_post_and_conflict(self):
        first,second=self.post(),self.post()
        self.assertEqual(first.status_code,201)
        self.assertEqual(second.status_code,201)
        self.assertNotEqual(first.json()['run_id'],second.json()['run_id'])
        self.request['assumptions']['inflation']=Decimal('0.05')
        response=self.post()
        self.assertEqual(response.status_code,409)
        self.assertEqual(response.json()['error']['code'],'ASSUMPTION_VERSION_CONFLICT')
        with self.repo.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM economic_scenarios.run').fetchone()[0],2)

    def test_invalid_input_leaves_no_run(self):
        for field,value in [('inflation',True),('inflation','0.04'),('inflation',Decimal('0.123456789'))]:
            self.request['assumptions'][field]=value
            response=self.post()
            self.assertEqual(response.status_code,422)
            self.assertEqual(response.json()['error']['code'],'INVALID_ASSUMPTION')
        with self.repo.connect() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM economic_scenarios.run').fetchone()[0],0)

    def test_unknown_rules_and_uuid(self):
        self.request['ruleset_id']='absent'
        self.assertEqual(self.post().status_code,422)
        for path in ('runs','scenarios'):
            response=self.client.get('/api/v1/'+path+'/'+str(uuid4()))
            self.assertEqual(response.status_code,404)
            self.assertEqual(self.client.get('/api/v1/'+path+'/invalid').status_code,422)

    def test_unavailable_database_and_health(self):
        import psycopg
        with patch.object(self.repo,'connect',side_effect=psycopg.OperationalError('secret')):
            self.assertEqual(self.client.get('/health').status_code,200)
            response=self.post()
            self.assertEqual(response.status_code,503)
            self.assertEqual(response.json()['error']['code'],'STORAGE_UNAVAILABLE')
            self.assertNotIn('secret',response.text)
