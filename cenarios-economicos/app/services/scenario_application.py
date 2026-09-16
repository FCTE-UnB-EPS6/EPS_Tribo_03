"""Orquestração de geração, configuração e persistência, independente de HTTP."""
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4
from app.services.scenario_generator import (
    generate_scenarios, loads_decimal, validate_request, ScenarioError, fail,
)


class RulesCatalog:
    def __init__(self, paths):
        self._rules = {}
        for path in paths:
            try:
                rules = loads_decimal(path.read_text())
                key = (rules['ruleset_id'], rules['ruleset_version'])
                if key in self._rules:
                    fail('INVALID_RULESET', None, 'Configuração duplicada no catálogo.')
                self._rules[key] = rules
            except (OSError, KeyError, TypeError, ScenarioError):
                fail('INVALID_RULESET', None, 'Catálogo de regras inválido ou indisponível.')

    def get(self, ruleset_id, version):
        rules = self._rules.get((ruleset_id, version))
        if rules is None:
            fail('RULESET_NOT_FOUND', 'ruleset_id', 'ID e versão não disponíveis no catálogo.')
        return deepcopy(rules)


def validated_uuid(value, field):
    try:
        if not isinstance(value, str):
            raise ValueError
        return str(UUID(value))
    except ValueError:
        fail('INVALID_REQUEST', field, 'Identificador UUID inválido.')


class ScenarioApplication:
    def __init__(self, repository, catalog):
        self.repository, self.catalog = repository, catalog

    def generate(self, request):
        validate_request(request)
        rules = self.catalog.get(request['ruleset_id'], request['ruleset_version'])
        result = generate_scenarios(request, rules)
        result['run_id'] = str(uuid4())
        result['created_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        result['status'] = 'completed'
        for scenario in result['scenarios']:
            scenario['scenario_id'] = str(uuid4())
        self.repository.save(result)
        # Nunca entregar status completed ao consumidor antes do commit.
        return result

    def get_run(self, run_id):
        return self.repository.get_run(validated_uuid(run_id, 'run_id'))

    def get_scenario(self, scenario_id):
        return self.repository.get_scenario(validated_uuid(scenario_id, 'scenario_id'))
