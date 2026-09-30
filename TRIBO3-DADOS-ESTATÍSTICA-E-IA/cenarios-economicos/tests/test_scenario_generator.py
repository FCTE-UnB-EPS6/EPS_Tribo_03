from copy import deepcopy
from decimal import Decimal, localcontext
from pathlib import Path
import unittest
from app.services.scenario_generator import ScenarioError, dumps_decimal, generate_scenarios, loads_decimal

ROOT = Path(__file__).resolve().parents[1]

class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.request = loads_decimal((ROOT/'examples/generate.demo.v0.1.0.json').read_text())
        self.rules = loads_decimal((ROOT/'config/scenario_rules.demo.v0.1.0.json').read_text())

    def generate(self):
        return generate_scenarios(self.request, self.rules)

    def error(self, code):
        with self.assertRaises(ScenarioError) as caught:
            self.generate()
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(set(caught.exception.as_dict()['error']), {'code', 'field', 'message'})

    def test_golden_values_and_periods(self):
        expected = [('base', ['0.04','0.08','0.045','0.09']),
                    ('adverse', ['0.06','0.06','0.055','0.06']),
                    ('favorable', ['0.03','0.09','0.04','0.11'])]
        result = self.generate()
        self.assertEqual(len(result['scenarios']), 3)
        for scenario, (key, rates) in zip(result['scenarios'], expected):
            self.assertEqual(scenario['scenario_key'], key)
            self.assertEqual(len(scenario['values']), 10)
            for i, row in enumerate(scenario['values'], 1):
                self.assertEqual(row['period'], i)
                self.assertEqual(row['period_start'], f'{2025+i}-09-13')
                self.assertEqual(row['period_end'], f'{2026+i}-09-13')
                self.assertEqual(list(row['variables'].values()), list(map(Decimal, rates)))

    def test_reproduction_and_isolation(self):
        original = deepcopy((self.request,self.rules))
        first, second = self.generate(), self.generate()
        self.assertEqual(dumps_decimal(first), dumps_decimal(second))
        first['request_snapshot']['sources']['inflation']['description']='changed'
        first['ruleset_snapshot']['scenarios']['base']['adjustments']['inflation']=1
        first['scenarios'][0]['values'][0]['variables']['inflation']=1
        self.assertEqual((self.request,self.rules), original)
        self.assertEqual(first['scenarios'][0]['values'][1]['variables']['inflation'],Decimal('0.04'))
        self.assertNotIn('run_id', second)
        self.assertNotIn('status', second)

    def test_decimal_roundtrip_and_context(self):
        self.request['assumptions']['inflation']=Decimal('0.12345678')
        with localcontext() as ctx:
            ctx.prec=3
            result=self.generate()
            self.assertEqual(result['scenarios'][1]['values'][0]['variables']['inflation'],Decimal('0.14345678'))
            self.assertEqual(loads_decimal(dumps_decimal(result)),result)
        self.assertIn(':0.14345678',dumps_decimal(result))

    def test_trailing_zero_and_additive_shock(self):
        self.request['assumptions']['inflation']=Decimal('0.040000000000')
        self.rules['scenarios']['adverse']['adjustments']['inflation']=Decimal('0.010000000')
        self.assertEqual(self.generate()['scenarios'][1]['values'][0]['variables']['inflation'],Decimal('0.05'))

    def test_absent_optionals(self):
        for k in ('salary_growth','asset_return'):
            del self.request['assumptions'][k]
            del self.request['sources'][k]
        for s in self.generate()['scenarios']:
            for row in s['values']:
                self.assertEqual(set(row['variables']),{'inflation','discount_rate'})

    def test_leap_anniversary(self):
        self.request.update(base_date='2024-02-29',horizon_years=4)
        rows=self.generate()['scenarios'][0]['values']
        self.assertEqual(rows[0]['period_start'],'2024-02-29')
        self.assertEqual([r['period_end'] for r in rows],['2025-02-28','2026-02-28','2027-02-28','2028-02-29'])
        self.assertTrue(all(a['period_end']==b['period_start'] for a,b in zip(rows,rows[1:])))

    def test_horizon(self):
        for n in (1,120):
            self.request['horizon_years']=n
            self.assertEqual(len(self.generate()['scenarios'][0]['values']),n)
        for n in (0,-1,121,True,'10',Decimal('10'),None):
            with self.subTest(n=n):
                self.request['horizon_years']=n
                self.error('INVALID_REQUEST')

    def test_dates(self):
        for d in ('2026-02-29','20260913','2026-9-13',None,'9999-01-01'):
            with self.subTest(d=d):
                self.request['base_date']=d
                self.error('INVALID_REQUEST')

    def test_invalid_rates(self):
        for v in (True,None,'0.04',0.04,Decimal('NaN'),Decimal('Infinity'),-1,-2,Decimal('0.000000001')):
            with self.subTest(v=v):
                self.request['assumptions']['inflation']=v
                self.error('INVALID_ASSUMPTION')

    def test_valid_negative_rate(self):
        self.request['assumptions']['inflation']=Decimal('-0.5')
        self.assertEqual(self.generate()['scenarios'][0]['values'][0]['variables']['inflation'],Decimal('-0.5'))

    def test_invalid_result_atomicity(self):
        self.rules['scenarios']['favorable']['adjustments']['inflation']=Decimal('-1.04')
        original=deepcopy((self.request,self.rules))
        self.error('INVALID_SCENARIO')
        self.assertEqual((self.request,self.rules),original)

    def test_metadata(self):
        for field,value,code in [('contract_version','1.0.0','UNSUPPORTED_CONTRACT_VERSION'),
            ('unit','%','INVALID_REQUEST'),('rate_basis','real','INVALID_REQUEST'),
            ('assumption_set_id',' ','INVALID_REQUEST'),('assumption_version','latest','INVALID_REQUEST'),
            ('ruleset_version','01.0.0','INVALID_REQUEST')]:
            with self.subTest(field=field):
                old=self.request[field]; self.request[field]=value
                self.error(code)
                self.request[field]=old

    def test_fields(self):
        original=deepcopy(self.request)
        for field in original:
            with self.subTest(field=field):
                self.request=deepcopy(original); del self.request[field]
                self.error('INVALID_REQUEST')
        self.request=deepcopy(original); self.request['unexpected']=1
        self.error('INVALID_REQUEST')
        self.request=deepcopy(original); self.request['assumptions']['unknown']=0
        self.error('INVALID_ASSUMPTION')
        self.request=deepcopy(original); del self.request['assumptions']['inflation']
        self.error('INVALID_ASSUMPTION')

    def test_sources(self):
        original=deepcopy(self.request)
        for field in original['sources']['inflation']:
            self.request=deepcopy(original); del self.request['sources']['inflation'][field]
            self.error('INVALID_REQUEST')
        for field,value in [('kind','unknown'),('reference_date','2026-02-30'),('responsible','')]:
            self.request=deepcopy(original); self.request['sources']['inflation'][field]=value
            self.error('INVALID_REQUEST')
        self.request=deepcopy(original); del self.request['sources']['inflation']
        self.error('INVALID_REQUEST')
        self.request=deepcopy(original); self.request['sources']['unknown']={}
        self.error('INVALID_REQUEST')

    def test_rules_identity_structure(self):
        self.rules['ruleset_version']='0.2.0'; self.error('RULESET_NOT_FOUND')
        self.setUp(); del self.rules['scenarios']['base']; self.error('INVALID_RULESET')
        self.setUp(); self.rules['unexpected']=1; self.error('INVALID_RULESET')
        self.setUp(); self.rules['scenarios']['base']['adjustments']['inflation']=Decimal('0.01')
        self.error('INVALID_RULESET')

    def test_bad_adjustments(self):
        original=deepcopy(self.rules)
        for v in (None,True,'0.01',Decimal('NaN'),Decimal('0.000000001')):
            self.rules=deepcopy(original); self.rules['scenarios']['adverse']['adjustments']['inflation']=v
            self.error('INVALID_RULESET')
        self.rules=deepcopy(original); del self.rules['scenarios']['adverse']['adjustments']['inflation']
        self.error('INVALID_RULESET')
        self.rules=deepcopy(original); self.rules['scenarios']['adverse']['adjustments']['unknown']=0
        self.error('INVALID_RULESET')

    def test_non_objects(self):
        for bad in (None,[],True,10):
            self.request=bad; self.error('INVALID_REQUEST')
        self.setUp(); self.rules=[]; self.error('INVALID_RULESET')

    def test_json_validation(self):
        for text in ('{"x":NaN}','{"x":Infinity}','{"x":1,"x":2}','{',''):
            with self.subTest(text=text):
                with self.assertRaises(ScenarioError) as caught:
                    loads_decimal(text)
                self.assertEqual(caught.exception.code,'INVALID_JSON')
        for value in (0.04,float('nan'),Decimal('Infinity')):
            with self.assertRaises(ScenarioError):
                dumps_decimal({'x':value})

if __name__=='__main__':
    unittest.main()
