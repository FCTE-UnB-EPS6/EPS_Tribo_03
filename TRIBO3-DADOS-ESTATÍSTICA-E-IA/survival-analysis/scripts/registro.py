"""Rastreabilidade das entradas e do código, sem credenciais de conexão."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

VERSAO_MODELO = '0.2.1'
NOTA_USO = ('A estimativa individual é insumo para gestão de risco coletivo, '
            'nunca decisão automática sobre direitos individuais.')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ambiente():
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        try:
            return subprocess.check_output(['git', '-C', str(root), *args], text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    versions = {}
    for name in ['lifelines', 'scikit-survival', 'scikit-learn', 'pandas', 'numpy',
                 'matplotlib', 'scipy', 'psycopg2-binary', 'joblib']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'versao_modelo': VERSAO_MODELO, 'python': sys.version.split()[0],
            'git_commit': git('rev-parse', 'HEAD'),
            'git_modificado': bool(git('status', '--porcelain')),
            'scripts_sha256': {str(p.relative_to(Path(__file__).parents[1])): sha256(p)
                for p in [Path(__file__).parents[1]/'main.py', *sorted(Path(__file__).parent.glob('*.py'))]},
            'bibliotecas': versions}


def salvar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def validar_procedencia(dataset, permitir_fixture=False):
    """Somente extração rastreada do banco pode gerar relatório oficial.

    O manifesto identifica bytes e declaração do operador, não prova que o
    lote foi calibrado: o fechamento ainda exige revisão do Passo 1.
    """
    import pandas as pd
    import numpy as np
    from .avaliacao import COVARIAVEIS
    from .construir_dataset import construir_dataset_analitico
    dataset = Path(dataset)
    manifesto = dataset.with_suffix('.metadata.json')
    if not manifesto.exists():
        raise ValueError('Manifesto ausente; refaça a extração via main.py')
    meta = json.loads(manifesto.read_text())
    if meta.get('dataset_sha256') != sha256(dataset):
        raise ValueError('Hash diverge do manifesto; refaça a extração')
    fonte = meta.get('fonte')
    if fonte != 'banco' and not (permitir_fixture and fonte == 'local'):
        raise ValueError('Relatório oficial exige fonte banco; fixture somente no código de testes')
    if fonte == 'banco' and not str(meta.get('identificacao_fonte', '')).strip():
        raise ValueError('Identificação do lote do Passo 1 ausente')
    df = pd.read_csv(dataset)
    obrigatorias = set(COVARIAVEIS + ['participante_id', 'data_nascimento', 'data_ingresso',
        'data_desligamento', 'data_obito', 'status_atual', 'sexo', 'plano_tipo', 'submassa',
        'data_fim', 'data_referencia', 'tempo_observado', 'evento', 'fonte_dados'])
    ausentes = sorted(obrigatorias-set(df.columns))
    if ausentes:
        raise ValueError(f'Colunas ausentes no snapshot: {ausentes}')
    if df.empty or 'fonte_dados' not in df or not df.fonte_dados.eq(fonte).all():
        raise ValueError('Dataset vazio ou fonte das linhas diverge do manifesto')
    referencias = pd.to_datetime(df.data_referencia, errors='raise')
    if referencias.isna().any() or referencias.nunique() != 1 or referencias.iloc[0] != pd.Timestamp(meta['data_referencia']):
        raise ValueError('Referência diverge do manifesto')
    if df.participante_id.isna().any() or df.participante_id.astype(str).str.strip().eq('').any():
        raise ValueError('IDs ausentes no snapshot')
    # Hash sozinho não valida o conteúdo: conferir alvos e atributos derivados
    # das datas/categorias também na reutilização, antes de ajustar modelos.
    reconstruido, excluidos = construir_dataset_analitico(df, meta['data_referencia'], True)
    if len(excluidos):
        raise ValueError('Snapshot analítico contém registros inconsistentes')
    for coluna in COVARIAVEIS + ['tempo_observado', 'evento']:
        valores = pd.to_numeric(df[coluna], errors='coerce').to_numpy(dtype=float)
        if not np.isfinite(valores).all() or not np.allclose(
                valores, reconstruido[coluna].to_numpy(dtype=float), rtol=0, atol=1e-9):
            raise ValueError(f'{coluna} inconsistente com datas/categorias do snapshot')
    if not pd.to_datetime(df.data_fim, errors='raise').eq(reconstruido.data_fim).all():
        raise ValueError('data_fim inconsistente com datas do snapshot')
    if len(df) != meta.get('n_analitico') or int(df.evento.sum()) != meta.get('n_obitos'):
        raise ValueError('Contagens divergem do manifesto')
    for sufixo, campo in [('.bruto.csv', 'bruto_sha256'), ('.exclusoes.csv', 'exclusoes_sha256')]:
        if campo in meta:
            arquivo = dataset.with_suffix(sufixo)
            if not arquivo.is_file() or sha256(arquivo) != meta[campo]:
                raise ValueError(f'Hash/arquivo {sufixo} diverge do manifesto')
    if 'n_bruto' in meta and 'n_excluidos' in meta:
        if meta['n_bruto'] != len(df)+meta['n_excluidos']:
            raise ValueError('Contagens de registros brutos/excluídos inconsistentes')
        exclusoes = dataset.with_suffix('.exclusoes.csv')
        if exclusoes.is_file():
            audit = pd.read_csv(exclusoes)
            if len(audit) != meta['n_excluidos'] or audit.participante_id.duplicated().any() or (
                    set(audit.participante_id) & set(df.participante_id)):
                raise ValueError('Exclusões divergem do snapshot/manifesto')
    return df, meta
