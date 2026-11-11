"""제공된 과목 I·II MD를 전체 미검수 문제은행으로 변환한다."""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

from backend.import_questions import EXCLUDED_KEYS, parse_questions

spec = importlib.util.spec_from_file_location('bank_sample_converter', Path(__file__).with_name('prepare_samples.py'))
converter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(converter)


def picture_options(asset_root, key):
    image = (asset_root.parent / 'source/figures/q_p13_1.png').read_bytes()
    if image[:8] != b'\x89PNG\r\n\x1a\n' or struct.unpack('>II', image[16:24]) != (715,260):
        raise ValueError('S1-Q028 원본 그림 크기가 바뀌어 보기 경계를 확인해야 합니다.')
    encoded = base64.b64encode(image).decode('ascii')
    views = [(0,0,355,125),(385,0,330,125),(0,130,355,130),(385,125,330,135)]
    options = {}
    for number, (x,y,width,height) in enumerate(views,1):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
               f'viewBox="{x} {y} {width} {height}" overflow="hidden">'
               f'<image width="715" height="260" href="data:image/png;base64,{encoded}"/></svg>')
        filename = hashlib.sha256(svg.encode()).hexdigest()[:16]+'.svg'
        folder = asset_root / key
        folder.mkdir(parents=True,exist_ok=True)
        (folder/filename).write_text(svg,encoding='utf-8')
        options[number] = [{'type':'image','src':f'/api/v1/question-assets/{key}/{filename}',
                            'alt':f'원본 그림 보기 {number}'}]
    return options


def build_bank(questions, answers, asset_root, samples):
    existing = {sample['question_key']:sample for sample in samples}
    records = []
    for key in sorted(answers):
        if key in EXCLUDED_KEYS:
            continue
        if key not in questions:
            raise ValueError(f'문제 본문을 찾을 수 없습니다: {key}')
        if key in existing:
            records.append(existing[key])
            continue
        question, answer = dict(questions[key]), answers[key]
        body = question['body']
        if key == 'S2-Q060':
            marker = re.search(r'(?m)^<!-- 주의: 스캔본',body)
            if not marker or question['page_start'] != 77:
                raise ValueError('S2-Q060 원본 페이지 경계가 바뀌었습니다.')
            # PDF77에서 네 보기까지 끝나며 뒤 조각은 누락된 다른 문항에 속한다.
            body = body[:marker.start()]
            question['page_end'] = 77
        stem, choices, notes = converter.split_question(body)
        if key == 'S1-Q028':
            stem = re.sub(r'(?m)^!\[[^\]]*\]\(figures/q_p13_1\.png\)\s*$', '', stem).strip()
            stem = stem.replace('않은','<u>않은</u>',1)
            options = picture_options(asset_root,key)
        else:
            if list(choices) != [1,2,3,4]:
                raise ValueError(f'보기 네 개를 확인해야 합니다: {key}')
            options = {n:converter.to_blocks(value,key,asset_root) for n,value in choices.items()}
        label = answer['label'].strip()
        if label not in '①②③④' or len(label)!=1:
            raise ValueError(f'단일 정답을 확인해야 합니다: {key}')
        correct = converter.CHOICES.index(label)+1
        records.append({'question_key':key,'chapter_key':question['chapter_key'],
            'source_number':question['source_number'],'status':'draft',
            'question_page_start':question['page_start'],'question_page_end':question['page_end'],
            'answer_page_start':answer['page_start'],'answer_page_end':answer['page_end'],
            'content_blocks':converter.to_blocks(stem,key,asset_root),
            'options':[{'option_number':n,'is_correct':n==correct,'content_blocks':blocks} for n,blocks in options.items()],
            'explanation_blocks':converter.to_blocks(answer['body'].strip(),key,asset_root),
            'review':{'user_verified':False,'source_notes':notes}})
    return records


def main():
    output = converter.OUTPUT
    questions,_ = converter.parse_document((output/'source/questions.md').read_text(encoding='utf-8'))
    answers,_ = converter.parse_document((output/'source/answers.md').read_text(encoding='utf-8'),answers=True)
    converter.apply_corrections({'questions':questions,'answers':answers},
        json.loads((output/'sample-corrections.json').read_text(encoding='utf-8')))
    samples = json.loads((output/'samples.json').read_text(encoding='utf-8'))
    records = build_bank(questions,answers,output/'assets',samples)
    expected = {f'S{subject}-Q{number:03}' for subject,total in [(1,50),(2,126)] for number in range(1,total+1)}-EXCLUDED_KEYS
    if {record['question_key'] for record in records} != expected:
        raise ValueError('전체 문항 수 또는 제외 목록이 일치하지 않습니다.')
    validated,skipped = parse_questions(records,output/'assets')
    assert len(validated)==167 and not skipped
    temporary = output/'questions.json.tmp'
    temporary.write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temporary.replace(output/'questions.json')
    summary = {'questions':len(records),'subject_1':50,'subject_2':117,'excluded':sorted(EXCLUDED_KEYS),
               'preserved_samples':len(samples),'user_verified':0,'status':'draft',
               'structural_fixes':['S1-Q028 original picture split into four views','S2-Q060 ends at PDF77']}
    (output/'bank-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))


if __name__ == '__main__':
    main()
