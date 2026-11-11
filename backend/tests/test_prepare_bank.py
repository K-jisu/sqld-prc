import importlib.util
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import pytest


@pytest.fixture
def bank():
    path = Path(__file__).parents[1] / 'scripts/prepare_bank.py'
    assert path.exists(), '전체 문항 변환기가 필요합니다.'
    spec = importlib.util.spec_from_file_location('prepare_bank', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row(key, body, page=1):
    subject, number = int(key[1]), int(key[-3:])
    return dict(question_key=key, chapter_key=f'S{subject}-C1', source_number=number,
                page_start=page, page_end=page, body=body, label='②')


def test_whole_bank_preserves_existing_samples_and_excludes_missing_questions(bank, tmp_path):
    key='S1-Q001'
    original={'question_key':key,'review':{'user_verified':False,'source_notes':'기존 교정 보존'}}
    questions={key:row(key,'변환하면 안 되는 기존 샘플'),
               'S2-Q001':row('S2-Q001','합성 질문\n① 가\n② 나\n③ 다\n④ 라'),
               'S2-Q061':row('S2-Q061','없는 문항의 조각')}
    answers={key:row(key,'기존 해설'),'S2-Q001':row('S2-Q001','합성 해설'),
             'S2-Q061':row('S2-Q061','제외 해설')}
    result=bank.build_bank(questions,answers,tmp_path/'assets',[original])
    assert result[0]==original
    assert [v['question_key'] for v in result]==[key,'S2-Q001']
    assert result[1]['status']=='draft' and result[1]['review']['user_verified'] is False
    assert [v['option_number'] for v in result[1]['options']]==[1,2,3,4]
    assert result[1]['options'][1]['is_correct']


def test_question_60_stops_before_missing_page_fragments(bank, tmp_path):
    key='S2-Q060'
    question=row(key,'합성 질문\n① A\n② B\n③ C\n④ D\n'
                     '<!-- 주의: 스캔본에서 뒤 페이지 누락 -->\n① 다른 문항 조각\n',77)
    question['page_end']=None
    result=bank.build_bank({key:question},{key:row(key,'합성 해설')},tmp_path/'assets',[])[0]
    assert result['question_page_end']==77
    assert '다른 문항' not in str(result['content_blocks']+result['options'])
    assert len(result['options'])==4


def test_image_only_options_preserve_four_distinct_original_views(bank,tmp_path):
    source=tmp_path/'source/figures';source.mkdir(parents=True)
    png=b'\x89PNG\r\n\x1a\n'+b'\x00'*8+struct.pack('>II',715,260)+b'original-image-bytes'
    (source/'q_p13_1.png').write_bytes(png)
    key='S1-Q028'
    result=bank.build_bank({key:row(key,'합성 질문\n\n![원본 보기](figures/q_p13_1.png)',17)},
                           {key:row(key,'합성 해설')},tmp_path/'assets',[])[0]
    assert len(result['options'])==4
    views=[]
    for option in result['options']:
        block=option['content_blocks'][0]
        path=tmp_path/'assets'/key/block['src'].rsplit('/',1)[-1]
        image=ET.fromstring(path.read_text(encoding='utf-8'))
        views.append(image.attrib['viewBox'])
        assert 'original-image-bytes' in __import__('base64').b64decode(next(iter(image)).attrib['href'].split(',',1)[1]).decode('latin1')
    assert len(set(views))==4
    assert not any(b['type']=='image' for b in result['content_blocks'])


def test_missing_question_outside_agreed_exclusions_is_rejected(bank,tmp_path):
    with pytest.raises(ValueError,match='S1-Q002'):
        bank.build_bank({}, {'S1-Q002':row('S1-Q002','해설')},tmp_path/'assets',[])
