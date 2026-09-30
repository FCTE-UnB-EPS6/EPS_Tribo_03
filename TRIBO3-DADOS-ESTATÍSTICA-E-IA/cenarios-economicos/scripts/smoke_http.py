"""Demonstração HTTP com persistência, executável dentro do container da API."""
import argparse
import json
from decimal import Decimal
from pathlib import Path
from urllib.request import Request, urlopen


def get(url):
    with urlopen(url, timeout=10) as response:
        assert response.status == 200
        return json.loads(response.read(), parse_float=Decimal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8000')
    parser.add_argument('--run-id', help='Consulta uma execução existente, sem gerar outra.')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    assert get(base+'/health') == {'status':'ok'}
    if args.run_id:
        result = get(base+'/api/v1/runs/'+args.run_id)
    else:
        payload = (Path(__file__).resolve().parents[1]/'examples/generate.demo.v0.1.0.json').read_bytes()
        with urlopen(Request(base+'/api/v1/scenarios/generate',data=payload,
                             headers={'Content-Type':'application/json'},method='POST'),timeout=10) as response:
            assert response.status == 201
            result = json.loads(response.read(),parse_float=Decimal)
            assert get(base+response.headers['Location']) == result
    assert result['status'] == 'completed'
    assert len(result['scenarios']) == 3
    for scenario in result['scenarios']:
        assert get(base+'/api/v1/scenarios/'+scenario['scenario_id']) == {'run_id':result['run_id'],'scenario':scenario}
    print(json.dumps({'status':'ok','run_id':result['run_id'],'scenarios':3}))


if __name__ == '__main__':
    main()
