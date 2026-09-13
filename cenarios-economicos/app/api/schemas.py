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


def success_response(schema, description):
    return {'description':description,'content':{'application/json':{'schema':schema}}}
