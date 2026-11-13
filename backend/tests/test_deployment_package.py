import importlib.util
import json
from pathlib import Path

import pytest


def packager():
    path = Path(__file__).resolve().parents[2] / 'scripts/prepare_vercel.py'
    assert path.is_file(), '비공개 배포 패키지 도구가 필요합니다.'
    spec = importlib.util.spec_from_file_location('prepare_vercel', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    for folder in ('frontend/app', 'backend/src/backend', 'deployment/api', 'data/private/phase2/assets/S1-Q001', 'data/private/study-materials'):
        (tmp_path / folder).mkdir(parents=True)
    for name, content in {
        'frontend/package.json': '{}', 'frontend/app/page.tsx': 'export default function Home() {}',
        'frontend/.env.local': 'PRIVATE_DATABASE_URL=secret', 'frontend/app/.env': 'secret',
        'frontend/app/book.pdf': 'private', 'backend/src/backend/main.py': 'app = object()',
        'deployment/api/index.py': 'from backend.main import app', 'deployment/vercel.json': '{}',
        'deployment/.vercelignore': '.env*', 'deployment/.python-version': '3.14',
        'data/private/phase2/assets/S1-Q001/table.svg': '<svg/>',
        'data/private/phase2/assets/S1-Q001/unused.svg': '<svg/>',
        'data/private/study-materials/data-modeling.pdf': '%PDF-fixture-model',
        'data/private/study-materials/sql.pdf': '%PDF-fixture-sql',
        'data/private/phase2/samples.json': json.dumps([{'content_blocks': [
            {'type': 'image', 'src': '/api/v1/question-assets/S1-Q001/table.svg'}]}]),
    }.items():
        (tmp_path / name).write_text(content, encoding='utf-8')
    return tmp_path


def test_package_contains_only_runtime_source_referenced_images_and_study_pdfs(source):
    output = source / 'data/private/vercel/test-project'
    packager().prepare(source, output, 'fastapi==0.162.0\n')
    assert (output / 'app/page.tsx').is_file()
    assert (output / 'server/backend/main.py').is_file()
    assert (output / 'question-assets/S1-Q001/table.svg').is_file()
    assert not (output / 'question-assets/S1-Q001/unused.svg').exists()
    assert not any('.env' in p.name for p in output.rglob('*'))
    assert sorted(p.relative_to(output).as_posix() for p in output.rglob('*.pdf')) == [
        'study-materials/data-modeling.pdf', 'study-materials/sql.pdf']
    assert not (output / 'data').exists()


def test_package_refuses_destination_outside_private_folder(source):
    with pytest.raises(ValueError, match='비공개'):
        packager().prepare(source, source / 'frontend/public/deploy', '')


def test_package_prefers_whole_bank_images_over_sample_subset(source):
    folder=source/'data/private/phase2/assets/S2-Q126';folder.mkdir()
    (folder/'last.svg').write_text('<svg/>',encoding='utf-8')
    (source/'data/private/phase2/questions.json').write_text(json.dumps([
        {'content_blocks':[{'type':'image','src':'/api/v1/question-assets/S2-Q126/last.svg'}]}
    ]),encoding='utf-8')
    output=source/'data/private/vercel/full-project'
    packager().prepare(source,output,'')
    assert (output/'question-assets/S2-Q126/last.svg').is_file()


@pytest.mark.parametrize('src', ['/api/v1/question-assets/../../.env', '/api/v1/question-assets/S1-Q001/missing.svg'])
def test_package_refuses_missing_or_escaping_asset(source, src):
    (source / 'data/private/phase2/samples.json').write_text(json.dumps([
        {'content_blocks': [{'type': 'image', 'src': src}]}]), encoding='utf-8')
    with pytest.raises(ValueError):
        packager().prepare(source, source / 'data/private/vercel/test-project', '')
