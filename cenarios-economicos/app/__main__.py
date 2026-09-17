"""Cliente local para demonstrar aplicação e armazenamento antes da API HTTP."""
import argparse
import os
from pathlib import Path
import sys
from app.repositories.scenario_repository import ScenarioRepository
from app.services.scenario_application import RulesCatalog, ScenarioApplication
from app.services.scenario_generator import loads_decimal, dumps_decimal, ScenarioError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules-dir', type=Path, default=Path(__file__).resolve().parents[1] / 'config')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('init-db')
    sub.add_parser('generate').add_argument('request', type=Path)
    sub.add_parser('get-run').add_argument('id')
    sub.add_parser('get-scenario').add_argument('id')
    args = parser.parse_args()
    dsn = os.environ.get('ESG_DATABASE_URL')
    if not dsn:
        parser.error('Defina ESG_DATABASE_URL para o PostgreSQL de destino.')
    repository = ScenarioRepository(dsn)
    try:
        if args.command == 'init-db':
            repository.initialize()
            print('{"status":"initialized"}')
            return 0
        catalog = RulesCatalog(sorted(args.rules_dir.glob('scenario_rules.*.json'))) if args.command == 'generate' else None
        application = ScenarioApplication(repository, catalog)
        if args.command == 'generate':
            result = application.generate(loads_decimal(args.request.read_text()))
        elif args.command == 'get-run':
            result = application.get_run(args.id)
        else:
            result = application.get_scenario(args.id)
        print(dumps_decimal(result))
        return 0
    except ScenarioError as exc:
        print(dumps_decimal(exc.as_dict()), file=sys.stderr)
        return 1
    except OSError:
        print('{"error":{"code":"INVALID_REQUEST","field":null,"message":"Não foi possível ler o arquivo de entrada."}}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
