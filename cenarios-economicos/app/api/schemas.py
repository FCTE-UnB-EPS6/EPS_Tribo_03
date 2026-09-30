"""Descrições OpenAPI; a validação de domínio permanece no núcleo decimal."""
from copy import deepcopy
from pathlib import Path
import json

STRING = {'type': 'string', 'minLength': 1}
RATE = {'type': 'number', 'exclusiveMinimum': -1, 'description': 'Taxa nominal anual em fração decimal, até oito casas decimais.'}
VARIABLES = {'type': 'object', 'additionalProperties': False,
             'required': ['inflation', 'discount_rate'],
             'properties': {key: RATE for key in ('inflation', 'discount_rate', 'salary_growth', 'asset_return')}}
SOURCE = {'type': 'object', 'additionalProperties': False,
          'required': ['kind','reference','reference_version','reference_date','description','rationale','responsible'],
          'properties': {key: STRING for key in ('reference','reference_version','description','rationale','responsible')}}
SOURCE['properties'] = {**SOURCE['properties'], 'kind': {'enum': ['synthetic','external'], 'type':'string'},
                        'reference_date': {'type':'string','format':'date'}}
INPUT = {'type':'object', 'additionalProperties':False, 'properties': {
    'contract_version': {'type':'string','const':'0.1.0'},
    'base_date': {'type':'string','format':'date'},
    'horizon_years': {'type':'integer','minimum':1,'maximum':120},
    'unit': {'type':'string','const':'annual_decimal'},
    'rate_basis': {'type':'string','const':'nominal'},
    'assumption_set_id': STRING, 'assumption_version': {'type':'string','pattern':r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'},
    'ruleset_id': STRING, 'ruleset_version': {'type':'string','pattern':r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'},
    'assumptions': VARIABLES,
    'sources': {'type':'object','additionalProperties':False,'required':['inflation','discount_rate'],
                'properties': {key: SOURCE for key in VARIABLES['properties']}}
}}
INPUT['required'] = list(INPUT['properties'])
EXAMPLE = json.loads((Path(__file__).resolve().parents[2]/'examples/generate.demo.v0.1.0.json').read_text())
VERSION = {'type':'string','pattern':r'^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'}
TRAJECTORY_SOURCE = {'type':'object','additionalProperties':False,
    'required':['kind','reference','reference_version','reference_date','path'],
    'properties':{'kind':{'type':'string','enum':['calibration_artifact','model']},
        'reference':STRING,'reference_version':VERSION,
        'reference_date':{'type':'string','format':'date'},'path':STRING}}
TRAJECTORY_VARIABLE = {'type':'object','additionalProperties':False,
    'required':['value','status','measure','source_metric','method','source'],
    'properties':{'value':RATE,'status':{'type':'string','enum':['observed','market_implied','modeled']},
        'measure':{'type':'string','enum':['effective_return','annual_rate_level','forward_rate','level_change','modeled_rate']},
        'source_metric':STRING,'method':STRING,'source':TRAJECTORY_SOURCE}}
TRAJECTORY_VARIABLES = {'type':'object','additionalProperties':False,
    'required':['inflation','discount_rate'],
    'properties':{key:deepcopy(TRAJECTORY_VARIABLE) for key in ('inflation','discount_rate','salary_growth','asset_return')}}
CALIBRATION_REFERENCE = {'type':'object','additionalProperties':False,
    'required':['artifact_id','calibration_id','calibration_version','artifact_schema_version',
        'transformation_policy_version','cutoff_date','sha256','scope'],
    'properties':{'artifact_id':STRING,'calibration_id':STRING,'calibration_version':VERSION,
        'artifact_schema_version':VERSION,'transformation_policy_version':VERSION,
        'cutoff_date':{'type':'string','format':'date'},
        'sha256':{'type':'string','pattern':'^[0-9a-f]{64}$'},
        'scope':{'type':'string','enum':['historical_only','historical_and_market_implied']}}}
TRAJECTORY_PERIOD = {'type':'object','additionalProperties':False,
    'required':['period','period_start','period_end','variables'],
    'properties':{'period':{'type':'integer','minimum':1},
        'period_start':{'type':'string','format':'date'},'period_end':{'type':'string','format':'date'},
        'variables':TRAJECTORY_VARIABLES}}
TRAJECTORY_INPUT = {'type':'object','additionalProperties':False,
    'required':['contract_version','purpose','base_date','horizon_years','unit','rate_basis',
        'ruleset_id','ruleset_version','calibration','trajectory'],
    'properties':{'contract_version':{'type':'string','const':'0.2.0'},
        'purpose':{'type':'string','enum':['projection','backtest']},
        'base_date':{'type':'string','format':'date'},
        'horizon_years':{'type':'integer','minimum':1,'maximum':120},
        'unit':{'type':'string','const':'annual_decimal'},'rate_basis':{'type':'string','const':'nominal'},
        'ruleset_id':STRING,'ruleset_version':VERSION,'calibration':CALIBRATION_REFERENCE,
        'trajectory':{'type':'object','additionalProperties':False,
            'required':['trajectory_id','trajectory_version','periods'],
            'properties':{'trajectory_id':STRING,'trajectory_version':VERSION,
                'periods':{'type':'array','minItems':1,'maxItems':120,'items':TRAJECTORY_PERIOD}}}}}
TRAJECTORY_EXAMPLE = json.loads((Path(__file__).resolve().parents[2]/'examples/trajectory.demo.v0.2.0.json').read_text())
GENERATION_INPUT = {'oneOf':[INPUT,TRAJECTORY_INPUT], 'discriminator':{'propertyName':'contract_version'}}
ERROR = {'type':'object','required':['error'],'properties':{'error':{
    'type':'object','required':['code','field','message'], 'properties':{
        'code':STRING,'field':{'anyOf':[{'type':'string'},{'type':'null'}]},'message':STRING}}}}


def error_responses():
    return {status: {'description': description, 'content': {'application/json': {'schema':deepcopy(ERROR)}}}
            for status,description in {400:'JSON inválido',404:'Recurso não encontrado',405:'Método não permitido',
                409:'Conflito de versão',415:'Content-Type não suportado',422:'Entrada inválida',
                500:'Erro interno ou configuração inválida',503:'Armazenamento indisponível'}.items()}

SCENARIO = {'type':'object','required':['scenario_id','scenario_key','label','scenario_version',
    'base_date','horizon_years','unit','rate_basis','values'], 'properties':{
    'scenario_id':{'type':'string','format':'uuid'}, 'scenario_key':{'type':'string','enum':['base','adverse','favorable']},
    'label':STRING, 'scenario_version':STRING, 'base_date':{'type':'string','format':'date'},
    'horizon_years':INPUT['properties']['horizon_years'], 'unit':INPUT['properties']['unit'],
    'rate_basis':INPUT['properties']['rate_basis'], 'values':{'type':'array','items':{
        'type':'object','required':['period','period_start','period_end','variables'], 'properties':{
            'period':{'type':'integer','minimum':1}, 'period_start':{'type':'string','format':'date'},
            'period_end':{'type':'string','format':'date'}, 'variables':VARIABLES}}}}}
RUN = {'type':'object','required':['run_id','status','created_at','contract_version','generator_version',
    'request_snapshot','ruleset_snapshot','scenarios'], 'properties':{
    'run_id':{'type':'string','format':'uuid'},'status':{'type':'string','const':'completed'},
    'created_at':{'type':'string','format':'date-time'},'contract_version':INPUT['properties']['contract_version'],
    'generator_version':STRING, 'request_snapshot':INPUT, 'ruleset_snapshot':{'type':'object'},
    'scenarios':{'type':'array','minItems':3,'maxItems':3,'items':SCENARIO}}}
SCENARIO_LOOKUP = {'type':'object','required':['run_id','scenario'], 'properties':{
    'run_id':{'type':'string','format':'uuid'},'scenario':SCENARIO}}

SCENARIO_V02 = deepcopy(SCENARIO)
SCENARIO_V02['required'] += ['trajectory_id','trajectory_version']
SCENARIO_V02['properties'].update({'trajectory_id':STRING,'trajectory_version':VERSION})
RUN_V02 = deepcopy(RUN)
RUN_V02['properties']['contract_version'] = {'type':'string','const':'0.2.0'}
RUN_V02['properties']['request_snapshot'] = TRAJECTORY_INPUT
RUN_V02['properties']['scenarios'] = {'type':'array','minItems':3,'maxItems':3,'items':SCENARIO_V02}
GENERATION_RUN = {'oneOf':[RUN,RUN_V02], 'discriminator':{'propertyName':'contract_version'}}
SCENARIO_LOOKUP_V02 = {'type':'object','required':['run_id','scenario'],
    'properties':{'run_id':{'type':'string','format':'uuid'},'scenario':SCENARIO_V02}}
GENERATION_SCENARIO_LOOKUP = {'oneOf':[SCENARIO_LOOKUP,SCENARIO_LOOKUP_V02]}


def success_response(schema, description):
    return {'description':description,'content':{'application/json':{'schema':schema}}}
