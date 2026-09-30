"""FastAPI com parsing e serialização decimais exatos."""
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.responses import Response
from app.api.schemas import (GENERATION_INPUT, EXAMPLE, TRAJECTORY_EXAMPLE,
                             GENERATION_RUN, GENERATION_SCENARIO_LOOKUP,
                             error_responses, success_response)
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_application import RulesCatalog, ScenarioApplication
from app.services.scenario_generator import ScenarioError, loads_decimal, dumps_decimal

STATUS = {'INVALID_JSON':400, 'INVALID_REQUEST':422, 'INVALID_ASSUMPTION':422,
          'UNSUPPORTED_CONTRACT_VERSION':422, 'RULESET_NOT_FOUND':422, 'INVALID_SCENARIO':422,
          'RUN_NOT_FOUND':404, 'SCENARIO_NOT_FOUND':404, 'ASSUMPTION_VERSION_CONFLICT':409,
          'INVALID_RULESET':500, 'INTERNAL_ERROR':500, 'STORAGE_UNAVAILABLE':503,
          'INVALID_TRAJECTORY_REQUEST':422, 'INVALID_CALIBRATION_REFERENCE':422,
          'INVALID_TRAJECTORY':422, 'INVALID_TRAJECTORY_VALUE':422,
          'UNSUPPORTED_TRAJECTORY_CONTRACT_VERSION':422,
          'TRAJECTORY_VERSION_CONFLICT':409,
          'UNSUPPORTED_MEDIA_TYPE':415}


def json_response(content, status=200, headers=None):
    return Response(dumps_decimal(content), status_code=status, media_type='application/json', headers=headers)


def create_app(application=None):
    if application is None:
        dsn = os.environ.get('ESG_DATABASE_URL')
        if not dsn:
            raise RuntimeError('Defina ESG_DATABASE_URL antes de iniciar a API.')
        rules_dir = Path(os.environ.get('ESG_RULES_DIR', Path(__file__).resolve().parents[1]/'config'))
        application = ScenarioApplication(ScenarioRepository(dsn),
                                          RulesCatalog(sorted(rules_dir.glob('scenario_rules.*.json'))))
    api = FastAPI(title='Economic Scenario Generator', version='0.2.0',
                  description='Cenários determinísticos para premissas escalares 0.1.0 e trajetórias calibradas 0.2.0. Taxas em fração decimal nominal anual.')
    api.state.application = application

    @api.exception_handler(ScenarioError)
    async def domain_error(request, exc):
        return json_response(exc.as_dict(), STATUS.get(exc.code,500))

    @api.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return json_response(ScenarioError('INVALID_REQUEST',None,'Requisição inválida.').as_dict(),422)

    @api.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = {404:'ROUTE_NOT_FOUND',405:'METHOD_NOT_ALLOWED'}.get(exc.status_code,'INVALID_REQUEST')
        return json_response(ScenarioError(code,None,'Rota ou método HTTP não disponível.').as_dict(),exc.status_code,exc.headers)

    @api.exception_handler(Exception)
    async def unexpected_error(request, exc):
        return json_response(ScenarioError('INTERNAL_ERROR',None,'Não foi possível concluir a requisição.').as_dict(),500)

    @api.get('/health', summary='Verificar processo', response_class=Response, responses={200: success_response({'type':'object','properties':{'status':{'const':'ok','type':'string'}},'required':['status']}, 'Processo disponível; não verifica banco.')})
    def health():
        return json_response({'status':'ok'})

    @api.post('/api/v1/scenarios/generate', status_code=201, response_class=Response,
              summary='Gerar e persistir três cenários', responses={
                  **error_responses(),201:{'description':'Execução persistida com snapshots e três cenários.',
                    'headers':{'Location':{'schema':{'type':'string'},'description':'URL relativa de consulta da execução.'}},
                    'content':{'application/json':{'schema':GENERATION_RUN}}}},
              openapi_extra={'requestBody':{'required':True,'content':{'application/json':{
                  'schema':GENERATION_INPUT,'examples':{
                      'contract_0_1_0':{'summary':'Premissas escalares sintéticas','value':EXAMPLE},
                      'contract_0_2_0':{'summary':'Trajetória calibrada','value':TRAJECTORY_EXAMPLE}}}}}})
    async def generate(request: Request):
        if request.headers.get('content-type','').split(';',1)[0].strip().lower() != 'application/json':
            raise ScenarioError('UNSUPPORTED_MEDIA_TYPE',None,'Envie Content-Type: application/json.')
        # Não usar request.json(): sua conversão para float perderia precisão.
        try:
            payload = loads_decimal((await request.body()).decode('utf-8'))
        except UnicodeDecodeError:
            raise ScenarioError('INVALID_JSON',None,'JSON deve usar UTF-8.') from None
        result = await run_in_threadpool(application.generate, payload)
        return json_response(result,201,{'Location':f"/api/v1/runs/{result['run_id']}"})

    @api.get('/api/v1/runs/{run_id}', response_class=Response, responses={**error_responses(),200:success_response(GENERATION_RUN, 'Execução persistida.')},
             summary='Consultar execução e evidências')
    def get_run(run_id: str):
        return json_response(application.get_run(run_id))

    @api.get('/api/v1/scenarios/{scenario_id}', response_class=Response, responses={**error_responses(),200:success_response(GENERATION_SCENARIO_LOOKUP, 'Cenário persistido.')},
             summary='Consultar cenário e execução de origem')
    def get_scenario(scenario_id: str):
        return json_response(application.get_scenario(scenario_id))

    return api
