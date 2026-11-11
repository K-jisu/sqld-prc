"""제공된 MD 형식에 한정한 2단계 준비. 출력은 항상 미검수 draft다."""

import csv
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import unicodedata
import zipfile


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "data" / "private" / "phase2"
CHOICES = "①②③④⑤"
SAMPLES = ["S1-Q001", "S1-Q007", "S1-Q027", "S1-Q037",
           "S2-Q011", "S2-Q015", "S2-Q055", "S2-Q100"]


def parse_document(text, answers=False):
    rows, pages = {}, []
    subject = chapter = current = None
    physical, printed = 0, None
    pattern = r"^### (\d+)\.\s*(.*)" if answers else r"^### 문제 (\d+)\s*(.*)"
    for number, line in enumerate(text.splitlines(), 1):
        page = re.fullmatch(r"<!-- p\.(\d+|\?)(?: \((.*?)\))? -->", line)
        if page:
            physical += 1
            explicit = re.fullmatch(r"physical (\d+)", page[2] or "")
            if explicit and int(explicit[1]) != physical:
                raise ValueError(f"physical page mismatch at line {number}")
            printed = None if page[1] == "?" else int(page[1])
            pages.append({"pdf_page": physical, "printed_page": printed})
            continue
        heading = re.match(r"^# 과목 ([ⅠⅡⅢ]+) ", line)
        if heading:
            subject = {"Ⅰ": 1, "Ⅱ": 2}.get(heading[1])
            chapter, current = None, None
            continue
        if line.startswith("# SQL 전문가"):
            subject, current = None, None
        heading = re.match(r"^## 제(\d+)장 (.*)", line)
        if heading:
            chapter = f"S{subject}-C{heading[1]}"
            current = None
            continue
        heading = re.match(pattern, line)
        if heading and subject:
            key = f"S{subject}-Q{int(heading[1]):03d}"
            if key in rows:
                raise ValueError(f"duplicate question: {key}")
            current = {"question_key": key, "subject_id": subject,
                       "chapter_key": chapter, "source_number": int(heading[1]),
                       "page_start": physical, "page_end": physical,
                       "printed_page_start": printed, "printed_page_end": printed,
                       "source_line": number, "label": heading[2], "body": "", "_locations": []}
            rows[key] = current
        elif current:
            if line.strip() in {"SQL Professional·developer", "(빈 페이지)"}:
                continue
            current["body"] += line + "\n"
            current["_locations"].append((physical, printed))
            if line.strip() and not line.startswith("<!--") and (answers or not line.startswith(">")):
                current["page_end"] = physical
                current["printed_page_end"] = printed
    for row in rows.values():
        locations = row.pop("_locations")
        if not answers:
            try:
                parts, _ = question_parts(row["body"])
            except ValueError:
                row["page_end"] = row["printed_page_end"] = None
                continue
            included = [n for lines in parts.values() for n, line in lines if line.strip()]
            if included:
                row["page_end"], row["printed_page_end"] = locations[max(included)]
    return rows, pages


def question_parts(body):
    parts, notes = {0: []}, []
    selected, fenced, annotation, tail_notes = 0, False, False, False
    for index, line in enumerate(body.splitlines()):
        if line.startswith("<!--"):
            continue
        if tail_notes:
            notes.append(line)
            continue
        if not fenced:
            if re.match(r"^>\s*(그림 내용|.*핵심정리)", line):
                annotation = True
            elif selected and (line.startswith(">") or line.startswith("**")):
                # shortcut: 이 교재 변환본의 보기 뒤 학습 상자, 다른 형식은 경계 재검수 필요.
                annotation, tail_notes = True, True
            elif annotation and line.strip() and not line.startswith(">"):
                annotation = False
            if annotation:
                notes.append(line)
                continue
            option = re.match(r"^([①②③④⑤])\s*(.*)", line)
            if option:
                selected = CHOICES.index(option[1]) + 1
                if selected in parts:
                    raise ValueError(f"duplicate option: {selected}")
                parts[selected] = [(index, option[2])]
                continue
        if line.startswith("```"):
            fenced = not fenced
        parts[selected].append((index, line))
    if fenced:
        raise ValueError("unclosed SQL fence")
    return parts, notes


def split_question(body):
    parts, notes = question_parts(body)
    return ("\n".join(line for _, line in parts.pop(0)).strip(),
            {n: "\n".join(line for _, line in lines).strip() for n, lines in parts.items()},
            "\n".join(notes).strip())


def wrap_text(text, limit):
    lines, current, width = [], "", 0
    for char in text:
        size = 2 if unicodedata.east_asian_width(char) in "WF" else 1
        if char == "\n" or width + size > limit:
            lines.append(current)
            current, width = "", 0
        if char != "\n":
            current += char
            width += size
    return lines + [current]


def table_svg(lines):
    cells = []
    for line in lines:
        row = [c.strip().replace("<br>", "\n") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if all(re.fullmatch(r":?-+:?", c) for c in row):
            continue
        cells.append([c.replace("\\|", "|") for c in row])
    columns = len(cells[0])
    if any(len(row) != columns for row in cells):
        raise ValueError("inconsistent table columns")
    width, y = columns * 310, 0
    shapes = []
    for row in cells:
        wrapped = [wrap_text(cell, 28) for cell in row]
        height = max(map(len, wrapped)) * 25 + 20
        for col, cell in enumerate(wrapped):
            x = col * 310
            shapes.append(f'<rect x="{x}" y="{y}" width="310" height="{height}" fill="white" stroke="#777"/>')
            for n, text in enumerate(cell):
                shapes.append(f'<text x="{x+12}" y="{y+29+n*25}">{html.escape(text)}</text>')
        y += height
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width+1}" height="{y+1}" viewBox="0 0 {width+1} {y+1}"><g font-family="Malgun Gothic, sans-serif" font-size="18">{"".join(shapes)}</g></svg>'


def underline_svg(text):
    plain = text.replace("<u>", "").replace("</u>", "")
    # 원문의 밑줄을 이미지 안에 보존한다. 임의 HTML을 블록에 넣지 않는다.
    tokens = re.split(r"(<u>|</u>)", text)
    x, y, underline = 12, 30, False
    shapes = []
    for token in tokens:
        if token in ("<u>", "</u>"):
            underline = token == "<u>"
            continue
        for char in token:
            size = 20 if unicodedata.east_asian_width(char) in "WF" else 10
            if x + size > 770 or char == "\n":
                x, y = 12, y + 30
            if char != "\n":
                style = ' text-decoration="underline"' if underline else ""
                shapes.append(f'<text x="{x}" y="{y}"{style}>{html.escape(char)}</text>')
                x += size
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="790" height="{y+15}" '
            f'viewBox="0 0 790 {y+15}"><title>{html.escape(plain)}</title>'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<g font-family="Malgun Gothic, sans-serif" font-size="20">{"".join(shapes)}</g></svg>')


def to_blocks(text, key, asset_root):
    folder = asset_root / key
    folder.mkdir(parents=True, exist_ok=True)
    blocks, paragraph = [], []

    def asset(svg, alt):
        name = hashlib.sha256(svg.encode()).hexdigest()[:16] + ".svg"
        (folder / name).write_text(svg, encoding="utf-8")
        return {"type": "image", "src": f"/api/v1/question-assets/{key}/{name}", "alt": alt}

    def flush():
        if paragraph:
            value = "\n".join(paragraph).strip()
            if "<u>" in value:
                blocks.append(asset(underline_svg(value), value.replace("<u>", "").replace("</u>", "")))
            elif re.match(r"^(ALTER\s+TABLE|SELECT\s+\*|INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b", value, re.I):
                blocks.append({"type": "sql", "text": value})
            else:
                blocks.append({"type": "text", "text": re.sub(r"\*\*(.*?)\*\*", r"\1", value)})
            paragraph.clear()

    lines, i = text.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError("unclosed SQL fence")
            blocks.append({"type": "sql", "text": "\n".join(code)})
        elif line.startswith("|"):
            flush()
            table = []
            while i < len(lines) and lines[i].startswith("|"):
                table.append(lines[i])
                i += 1
            blocks.append(asset(table_svg(table), "문항 또는 해설에 제시된 표"))
            continue
        elif line.startswith("!["):
            flush()
            match = re.fullmatch(r"!\[([^\]]*)\]\((figures/q_p\d+_\d+\.png)\)", line)
            if not match:
                raise ValueError(f"invalid image reference: {line}")
            name = Path(match[2]).name
            source = asset_root.parent / "source" / match[2]
            if not source.is_file():
                raise ValueError(f"missing image: {source}")
            shutil.copyfile(source, folder / name)
            blocks.append({"type": "image", "src": f"/api/v1/question-assets/{key}/{name}", "alt": match[1]})
        elif not line.strip():
            flush()
        else:
            paragraph.append(re.sub(r"^>\s?", "", line))
        i += 1
    flush()
    return blocks


def write_csv(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def apply_corrections(records, corrections):
    if not isinstance(corrections, list):
        raise ValueError("corrections must be a list")
    for change in corrections:
        if not isinstance(change, dict):
            raise ValueError("invalid correction")
        document, key, before, after = (change.get(name) for name in
                                        ("document", "question_key", "before", "after"))
        if not all(isinstance(value, str) for value in (document, key, before, after)):
            raise ValueError("invalid correction fields")
        row = records.get(document, {}).get(key)
        if row is None or not before or row["body"].count(before) != 1:
            raise ValueError(f"correction source mismatch: {document}/{key}")
        if before.count("\n") != after.count("\n"):
            raise ValueError(f"correction must preserve page mapping: {key}")
        row["body"] = row["body"].replace(before, after, 1)


def main():
    source = OUTPUT / "source"
    source.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ROOT / "SQL_자격검정실전문제_변환.zip") as archive:
        if archive.testzip():
            raise ValueError("damaged archive")
        documents = {}
        for entry in archive.infolist():
            if entry.filename.endswith(".md"):
                text = archive.read(entry).decode("utf-8-sig")
                kind = "questions" if "### 문제 " in text else "answers"
                if kind in documents:
                    raise ValueError(f"duplicate source document: {kind}")
                documents[kind] = text
                (source / f"{kind}.md").write_text(text, encoding="utf-8")
            elif re.fullmatch(r"figures/q_p\d+_\d+\.png", entry.filename):
                target = source / entry.filename
                target.parent.mkdir(exist_ok=True)
                target.write_bytes(archive.read(entry))
    questions, qpages = parse_document(documents["questions"])
    answers, apages = parse_document(documents["answers"], answers=True)
    corrections_path = OUTPUT / "sample-corrections.json"
    corrections = json.loads(corrections_path.read_text(encoding="utf-8")) if corrections_path.exists() else []
    apply_corrections({"questions": questions, "answers": answers}, corrections)
    write_csv(OUTPUT / "question-pages.csv", qpages)
    write_csv(OUTPUT / "answer-pages.csv", apages)
    inventory, anomalies = [], {}
    for key in sorted(questions.keys() | answers.keys()):
        question, answer = questions.get(key), answers.get(key)
        problems = []
        option_count = None
        if question:
            try:
                _, options, _ = split_question(question["body"])
                option_count = len(options)
                if list(options) != [1, 2, 3, 4]:
                    problems.append("option_numbers_need_review")
            except ValueError as error:
                problems.append(str(error))
        else:
            problems.append("missing_question_heading")
        if not answer:
            problems.append("missing_answer")
        elif not re.fullmatch("[" + CHOICES + "]", answer["label"].strip()):
            problems.append("answer_type_needs_review")
        if key in ("S2-Q069", "S2-Q079"):
            problems.append("incomplete_source_pages")
        if problems:
            anomalies[key] = problems
        meta = question or answer
        inventory.append({"question_key": key, "subject_id": meta["subject_id"],
                          "chapter_key": meta["chapter_key"], "source_number": meta["source_number"],
                          "question_page_start": question["page_start"] if question else None,
                          "question_page_end": question["page_end"] if question else None,
                          "question_printed_page": question["printed_page_start"] if question else None,
                          "answer_page_start": answer["page_start"] if answer else None,
                          "answer_page_end": answer["page_end"] if answer else None,
                          "answer_printed_page": answer["printed_page_start"] if answer else None,
                          "option_count": option_count, "status": "draft",
                          "issues": "; ".join(problems)})
    write_csv(OUTPUT / "inventory.csv", inventory)
    samples, review = [], ["# 2단계 샘플 검수 자료", "", "모든 샘플은 draft이며 사용자 원문 대조 전입니다.", ""]
    for key in SAMPLES:
        if key in anomalies:
            raise ValueError(f"unsafe sample {key}: {anomalies[key]}")
        question, answer = questions[key], answers[key]
        stem, options, notes = split_question(question["body"])
        asset_root = OUTPUT / "assets"
        choice = CHOICES.index(answer["label"].strip()) + 1
        sample = {"question_key": key, "chapter_key": question["chapter_key"],
                  "source_number": question["source_number"], "status": "draft",
                  "question_page_start": question["page_start"], "question_page_end": question["page_end"],
                  "answer_page_start": answer["page_start"], "answer_page_end": answer["page_end"],
                  "content_blocks": to_blocks(stem, key, asset_root),
                  "options": [{"option_number": n, "is_correct": n == choice,
                               "content_blocks": to_blocks(value, key, asset_root)} for n, value in options.items()],
                  "explanation_blocks": to_blocks(answer["body"].strip(), key, asset_root),
                  "review": {"user_verified": False, "source_notes": notes}}
        if len(sample["options"]) != 4 or not all(o["content_blocks"] for o in sample["options"]):
            raise ValueError(f"incomplete sample: {key}")
        samples.append(sample)
        review.extend([f"## {key}", "", f"문제 PDF {question['page_start']}~{question['page_end']} / 해설 PDF {answer['page_start']}~{answer['page_end']}",
                       "", stem, "", *[f"{CHOICES[n-1]}\n\n{value}\n" for n, value in options.items()],
                       f"정답: {answer['label']}", "", answer["body"].strip(), "",
                       "검수 결과는 user-review.md에 기록합니다.", ""])
    (OUTPUT / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review_text = "\n".join(review).replace("](figures/", "](source/figures/")
    (OUTPUT / "sample-review.generated.md").write_text(review_text, encoding="utf-8")
    user_review = OUTPUT / "user-review.md"
    if not user_review.exists():
        user_review.write_text("# 사용자 원문 대조 기록\n\n자동 생성 자료와 구분하며 재실행해도 덮어쓰지 않습니다.\n\n"
                               + "\n".join(f"- [ ] {key}: 본문·보기·정답·해설·SQL·이미지·밑줄 확인" for key in SAMPLES)
                               + "\n\n결정 대기: 누락 6쪽 확보 방법, 밑줄 이미지 표현, 핵심정리의 별도 학습자료 여부.\n", encoding="utf-8")
    summary = {"questions": len(questions), "answers": len(answers), "inventory": len(inventory),
               "question_pdf_pages": len(qpages), "answer_pdf_pages": len(apages),
               "samples": len(samples), "anomalies": anomalies,
                "corrections_applied": len(corrections),
               "user_verified_samples": 0,
               "source_zip_sha256": hashlib.sha256((ROOT / "SQL_자격검정실전문제_변환.zip").read_bytes()).hexdigest()}
    (OUTPUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
