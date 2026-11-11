import importlib.util
from pathlib import Path
import json
import zipfile

import pytest


SCRIPT = Path(__file__).parents[1] / "scripts" / "prepare_samples.py"


@pytest.fixture
def converter():
    assert SCRIPT.exists(), "샘플 변환 스크립트가 필요합니다"
    spec = importlib.util.spec_from_file_location("prepare_samples", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inventory_distinguishes_subjects_and_tracks_physical_pages(converter):
    source = """<!-- p.? (physical 001) -->
<!-- p.4 -->
# 과목 Ⅰ 예시
## 제1장 첫 단원
### 문제 1
합성 문항
① 가
② 나
<!-- p.5 -->
③ 다
④ 라
# 과목 Ⅱ 다른 예시
## 제1장 다른 단원
### 문제 1
다른 합성 문항
① 가
② 나
③ 다
④ 라
"""
    rows, pages = converter.parse_document(source)
    assert list(rows) == ["S1-Q001", "S2-Q001"]
    assert rows["S1-Q001"]["page_start"] == 2
    assert rows["S1-Q001"]["page_end"] == 3
    assert rows["S2-Q001"]["printed_page_start"] == 5
    assert pages[0] == {"pdf_page": 1, "printed_page": None}


def test_duplicate_question_keys_are_rejected(converter):
    with pytest.raises(ValueError, match="duplicate"):
        converter.parse_document("# 과목 Ⅰ 예시\n### 문제 1\n가\n### 문제 1\n나")


def test_annotated_page_markers_still_count_as_physical_pages(converter):
    rows, pages = converter.parse_document(
        "<!-- p.240 -->\n# 과목 Ⅱ 합성\n### 1. ②\n앞 해설\n"
        "<!-- p.241 (설명이 두 쪽에 걸침) -->\n뒤 해설\n<!-- p.242 -->\n### 2. ①\n다음 해설",
        answers=True,
    )
    assert len(pages) == 3
    assert rows["S2-Q001"]["page_end"] == 2
    assert rows["S2-Q002"]["page_start"] == 3


def test_following_page_study_box_is_not_the_question_page_end(converter):
    rows, _ = converter.parse_document(
        "<!-- p.4 -->\n# 과목 Ⅰ 합성\n### 문제 1\n본문\n① 가\n② 나\n③ 다\n④ 라\n"
        "<!-- p.5 -->\n> **핵심정리**\n> 다음 쪽의 학습 상자"
    )
    assert rows["S1-Q001"]["page_end"] == 1


def test_plain_study_box_and_blank_page_do_not_extend_question_range(converter):
    rows, _ = converter.parse_document(
        "<!-- p.4 -->\n# 과목 Ⅰ 합성\n### 문제 1\n본문\n① 가\n② 나\n③ 다\n④ 라\n"
        "<!-- p.5 -->\n**학습 상자**\n| 값 | 의미 |\n|---|---|\n| 가 | 나 |\n"
        "<!-- p.? (physical 003) -->\nSQL Professional·developer\n(빈 페이지)"
    )
    assert rows["S1-Q001"]["page_end"] == 1


def test_real_sql_continuation_extends_question_range(converter):
    rows, _ = converter.parse_document(
        "<!-- p.4 -->\n# 과목 Ⅰ 합성\n### 문제 1\n본문\n① 가\n② 나\n③ 다\n④\n"
        "```sql\nSELECT 1\n<!-- p.5 -->\n  FROM T;\n```\n"
        "<!-- p.6 -->\n**학습 상자**\n메모"
    )
    assert rows["S1-Q001"]["page_end"] == 2


def test_underline_is_preserved_without_html_in_text_blocks(converter, tmp_path):
    blocks = converter.to_blocks("조건에 <u>맞지 않는</u> 항목", "S1-Q001", tmp_path)
    assert blocks[0]["type"] == "image"
    assert blocks[0]["alt"] == "조건에 맞지 않는 항목"
    svg = next((tmp_path / "S1-Q001").glob("*.svg")).read_text(encoding="utf-8")
    assert 'text-decoration="underline"' in svg


def test_sql_option_symbols_do_not_split_choices(converter):
    body = """조건에 맞는 결과를 고르세요.
```sql
SELECT '①' AS 표시
  FROM 예시;
```
① 첫 결과
② 다음 결과
③ 셋째 결과
④ 마지막 결과
> 핵심정리: 문항과 구분할 학습 메모
"""
    stem, options, notes = converter.split_question(body)
    assert "SELECT '①' AS 표시\n  FROM 예시;" in stem
    assert list(options) == [1, 2, 3, 4]
    assert options[4] == "마지막 결과"
    assert "핵심정리" in notes


def test_repeated_choice_numbers_are_not_silently_overwritten(converter):
    with pytest.raises(ValueError, match="duplicate option"):
        converter.split_question("합성 문항\n① 가\n② 나\n① 고아 선택지")


def test_blocks_preserve_sql_and_escape_table_images(converter, tmp_path):
    blocks = converter.to_blocks(
        "문장\n\n```sql\nSELECT  1\n  FROM T;\n```\n\n"
        "| 값 | 설명 |\n|---|---|\n| <script> | A&B |",
        "S1-Q001",
        tmp_path,
    )
    assert blocks[0] == {"type": "text", "text": "문장"}
    assert blocks[1] == {"type": "sql", "text": "SELECT  1\n  FROM T;"}
    assert blocks[2]["type"] == "image"
    assert "/S1-Q001/" in blocks[2]["src"]
    svg = next((tmp_path / "S1-Q001").glob("*.svg")).read_text(encoding="utf-8")
    assert "&lt;script&gt;" in svg and "A&amp;B" in svg
    assert "<script>" not in svg


def test_image_paths_cannot_escape_the_provided_figures(converter, tmp_path):
    with pytest.raises(ValueError, match="image"):
        converter.to_blocks("![図](../../secret.png)", "S1-Q001", tmp_path)


def test_unclosed_sql_is_rejected_for_sample_conversion(converter, tmp_path):
    with pytest.raises(ValueError, match="unclosed"):
        converter.to_blocks("```sql\nSELECT 1", "S1-Q001", tmp_path)


def test_summary_table_does_not_become_the_last_option(converter):
    _, options, notes = converter.split_question(
        "합성 문항\n① 가\n② 나\n③ 다\n④ 라\n\n"
        "**핵심 참고표**\n\n| 의미 | 값 |\n|---|---|\n| 정답 힌트 | 내용 |"
    )
    assert options[4] == "라"
    assert "정답 힌트" in notes


def test_inline_sql_options_keep_their_layout(converter, tmp_path):
    blocks = converter.to_blocks("ALTER TABLE T ADD C INT;\n   ALTER TABLE T ADD D INT;", "S1-Q001", tmp_path)
    assert blocks == [{"type": "sql", "text": "ALTER TABLE T ADD C INT;\n   ALTER TABLE T ADD D INT;"}]


def test_private_corrections_change_only_the_target_record(converter):
    records = {"questions": {"S1-Q001": {"body": "합성 문항\n① 가"},
                              "S1-Q002": {"body": "다른 문항"}}, "answers": {}}
    converter.apply_corrections(records, [{"document": "questions", "question_key": "S1-Q001",
                                          "before": "합성 문항", "after": "합성 <u>문항</u>"}])
    assert records["questions"]["S1-Q001"]["body"] == "합성 <u>문항</u>\n① 가"
    assert records["questions"]["S1-Q002"]["body"] == "다른 문항"


@pytest.mark.parametrize("body,before,after", [
    ("바뀐 원문", "이전 원문", "교정"),
    ("원문 원문", "원문", "교정"),
    ("원문", "", "교정"),
    ("원문", "원문", "교정\n새 줄"),
])
def test_corrections_reject_stale_or_ambiguous_text(converter, body, before, after):
    records = {"questions": {"S1-Q001": {"body": body}}, "answers": {}}
    with pytest.raises(ValueError, match="correction"):
        converter.apply_corrections(records, [{"document": "questions", "question_key": "S1-Q001",
                                              "before": before, "after": after}])


def test_regeneration_preserves_user_review_and_keeps_samples_draft(converter, tmp_path):
    converter.ROOT = tmp_path
    converter.OUTPUT = tmp_path / "data" / "private" / "phase2"
    converter.SAMPLES = ["S1-Q001"]
    with zipfile.ZipFile(tmp_path / "SQL_자격검정실전문제_변환.zip", "w") as archive:
        archive.writestr("questions.md", "<!-- p.1 -->\n# 과목 Ⅰ 합성\n## 제1장 합성\n### 문제 1\n합성 문항\n①\n```sql\nSELECT 1;\n```\n② 나\n③ 다\n④ 라")
        archive.writestr("answers.md", "<!-- p.230 -->\n# 과목 Ⅰ 합성\n## 제1장 합성\n### 1. ②\n합성 해설")
    converter.OUTPUT.mkdir(parents=True)
    (converter.OUTPUT / "sample-corrections.json").write_text(json.dumps([
        {"document": "questions", "question_key": "S1-Q001", "before": "합성 문항", "after": "합성 <u>문항</u>"}
    ], ensure_ascii=False), encoding="utf-8")
    converter.main()
    generated = (converter.OUTPUT / "sample-review.generated.md").read_text(encoding="utf-8")
    assert "①\n\n```sql\nSELECT 1;\n```" in generated
    review = converter.OUTPUT / "user-review.md"
    assert review.is_file()
    review.write_text("사용자가 남긴 검수 기록", encoding="utf-8")
    before = (converter.OUTPUT / "samples.json").read_bytes()
    converter.main()
    assert review.read_text(encoding="utf-8") == "사용자가 남긴 검수 기록"
    assert (converter.OUTPUT / "samples.json").read_bytes() == before
    sample = json.loads(before)[0]
    assert sample["content_blocks"][0]["type"] == "image"
    assert "<u>" not in (converter.OUTPUT / "source/questions.md").read_text(encoding="utf-8")
    assert json.loads((converter.OUTPUT / "summary.json").read_text(encoding="utf-8"))["corrections_applied"] == 1
    assert sample["status"] == "draft"
    assert sample["review"]["user_verified"] is False
