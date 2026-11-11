from copy import deepcopy
import importlib

import pytest


def test_valid_draft_keeps_sql_whitespace(question_data, tmp_path):
    importer = importlib.import_module("backend.import_questions")
    question_data["content_blocks"] = [{"type": "sql", "text": "SELECT  1\n  FROM T;"}]
    parsed, skipped = importer.parse_questions([question_data], tmp_path)
    assert skipped == []
    assert parsed[0].status == "draft"
    assert parsed[0].content_blocks[0].text == "SELECT  1\n  FROM T;"


def test_duplicate_keys_are_rejected(question_data, tmp_path):
    importer = importlib.import_module("backend.import_questions")
    with pytest.raises(ValueError, match="duplicate"):
        importer.parse_questions([question_data, deepcopy(question_data)], tmp_path)


@pytest.mark.parametrize("defect", ["no_correct", "two_correct", "three_options", "wrong_order", "page_range", "key_number", "chapter_subject", "html_block", "question_page_overflow", "answer_page_overflow", "source_number_overflow"])
def test_invalid_question_is_rejected(question_data, tmp_path, defect):
    importer = importlib.import_module("backend.import_questions")
    if defect == "no_correct":
        question_data["options"][1]["is_correct"] = False
    elif defect == "two_correct":
        question_data["options"][0]["is_correct"] = True
    elif defect == "three_options":
        question_data["options"].pop()
    elif defect == "wrong_order":
        question_data["options"][0], question_data["options"][1] = question_data["options"][1], question_data["options"][0]
    elif defect == "page_range":
        question_data["question_page_start"] = 2
    elif defect == "key_number":
        question_data["source_number"] = 2
    elif defect == "chapter_subject":
        question_data["chapter_key"] = "S2-C1"
    elif defect == "question_page_overflow":
        question_data["question_page_end"] = 225
    elif defect == "answer_page_overflow":
        question_data["answer_page_end"] = 65
    elif defect == "source_number_overflow":
        question_data["source_number"], question_data["question_key"] = 51, "S1-Q051"
    else:
        question_data["content_blocks"] = [{"type": "html", "text": "<b>입력</b>"}]
    with pytest.raises(ValueError):
        importer.parse_questions([question_data], tmp_path)


def test_known_book_boundaries_are_accepted(question_data, tmp_path):
    importer = importlib.import_module("backend.import_questions")
    question_data.update(question_key="S2-Q126", source_number=126, chapter_key="S2-C3",
                         question_page_end=224, answer_page_end=64)
    parsed, _ = importer.parse_questions([question_data], tmp_path)
    assert parsed[0].source_number == 126
    question_data.update(question_key="S2-Q127", source_number=127)
    with pytest.raises(ValueError):
        importer.parse_questions([question_data], tmp_path)


def test_unverified_sample_cannot_be_published(question_data, tmp_path):
    importer = importlib.import_module("backend.import_questions")
    question_data["status"] = "published"
    with pytest.raises(ValueError):
        importer.parse_questions([question_data], tmp_path)
    question_data["review"]["user_verified"] = True
    parsed, _ = importer.parse_questions([question_data], tmp_path)
    assert parsed[0].status == "published"


@pytest.mark.parametrize("src", ["/api/v1/question-assets/S1-Q001/../../secret.png", "/api/v1/question-assets/S1-Q002/diagram.png", "/api/v1/question-assets/S1-Q001/missing.png"])
def test_unsafe_or_missing_images_are_rejected(question_data, tmp_path, src):
    importer = importlib.import_module("backend.import_questions")
    question_data["content_blocks"] = [{"type": "image", "src": src, "alt": "합성 그림"}]
    with pytest.raises(ValueError, match="image"):
        importer.parse_questions([question_data], tmp_path)


def test_question_key_asset_is_accepted(question_data, tmp_path):
    importer = importlib.import_module("backend.import_questions")
    directory = tmp_path / "S1-Q001"
    directory.mkdir()
    (directory / "diagram.png").write_bytes(b"synthetic fixture")
    question_data["content_blocks"] = [{"type": "image", "src": "/api/v1/question-assets/S1-Q001/diagram.png", "alt": "합성 그림"}]
    parsed, _ = importer.parse_questions([question_data], tmp_path)
    assert parsed[0].content_blocks[0].alt == "합성 그림"


def test_confirmed_missing_questions_are_skipped_before_content_validation(tmp_path):
    importer = importlib.import_module("backend.import_questions")
    parsed, skipped = importer.parse_questions([{"question_key": f"S2-Q{n:03d}"} for n in [61, 62, 63, 64, 69, 70, 79, 80, 81]], tmp_path)
    assert parsed == []
    assert skipped == [f"S2-Q{n:03d}" for n in [61, 62, 63, 64, 69, 70, 79, 80, 81]]
