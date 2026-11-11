"""Git 제외 폴더에 필요한 코드와 참조 이미지만 모아 비공개 배포를 준비한다."""

import json
from pathlib import Path
import re
import shutil
import subprocess
from uuid import uuid4


def prepare(root: Path, output: Path, requirements: str):
    root, output = root.resolve(), output.resolve()
    if not output.is_relative_to(root / 'data/private/vercel'):
        raise ValueError('배포 폴더는 비공개 data/private/vercel 안이어야 합니다.')
    assets = root / 'data/private/phase2/assets'
    references = set()

    def inspect(value):
        if isinstance(value, dict):
            if value.get('type') == 'image':
                src = value.get('src', '')
                match = re.fullmatch(r'/api/v1/question-assets/(S[12]-Q\d{3}/[\w.-]+\.(?:png|jpe?g|webp|svg))', src)
                if not match:
                    raise ValueError('배포 이미지 경로가 안전하지 않습니다.')
                relative = match[1]
                path = (assets / relative).resolve()
                if not path.is_relative_to(assets.resolve()) or not path.is_file():
                    raise ValueError('배포 이미지가 없거나 경로를 벗어났습니다.')
                references.add(relative)
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    data_directory = root / 'data/private/phase2'
    question_file = data_directory / 'questions.json'
    if not question_file.is_file():
        question_file = data_directory / 'samples.json'
    inspect(json.loads(question_file.read_text(encoding='utf-8')))
    output.mkdir(parents=True, exist_ok=False)
    suffixes = {'.ts', '.tsx', '.js', '.mjs', '.css', '.json', '.ico', '.svg', '.woff', '.woff2'}
    for folder in ('app', 'components', 'lib', 'public'):
        source = root / 'frontend' / folder
        for path in source.rglob('*'):
            if path.is_file() and path.suffix in suffixes and not path.name.startswith('.'):
                if not path.resolve().is_relative_to(source.resolve()):
                    raise ValueError('코드 파일이 원본 폴더를 벗어났습니다.')
                destination = output / folder / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, destination)
    for name in ('package.json', 'pnpm-lock.yaml', 'pnpm-workspace.yaml', 'next.config.ts', 'next-env.d.ts', 'tsconfig.json', 'eslint.config.mjs'):
        path = root / 'frontend' / name
        if path.is_file():
            shutil.copy2(path, output / name)
    shutil.copytree(root / 'backend/src/backend', output / 'server/backend',
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.env*'))
    for name in ('api', 'vercel.json', '.vercelignore', '.python-version'):
        source = root / 'deployment' / name
        if source.is_dir():
            shutil.copytree(source, output / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        else:
            shutil.copy2(source, output / name)
    for relative in references:
        destination = output / 'question-assets' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(assets / relative, destination)
    (output / 'requirements.txt').write_text(requirements, encoding='utf-8')
    return output


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(['uv', 'export', '--locked', '--no-dev', '--no-emit-project', '--no-hashes', '--format', 'requirements.txt'],
                            cwd=root / 'backend', capture_output=True, text=True, encoding='utf-8', check=True)
    output = prepare(root, root / 'data/private/vercel' / ('project-' + uuid4().hex[:12]), result.stdout)
    print(output)
