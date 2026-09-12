"""Rastreabilidade das entradas e do código, sem credenciais de conexão."""
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess


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
                 'matplotlib', 'scipy', 'psycopg2-binary']:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'git_commit': git('rev-parse', 'HEAD'),
            'git_modificado': bool(git('status', '--porcelain')),
            'scripts_sha256': {p.name: sha256(p) for p in sorted(Path(__file__).parent.glob('*.py'))},
            'bibliotecas': versions}


def salvar_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
