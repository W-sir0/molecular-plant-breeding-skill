#!/usr/bin/env python3
"""Read selected local PDF pages; output private, source-bound reading caches."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


def parse_pages(spec: str, count: int) -> list[int]:
    pages = set()
    for part in spec.split(','):
        match = re.fullmatch(r'\s*(\d+)(?:\s*-\s*(\d+))?\s*', part)
        if not match:
            raise ValueError(f'Invalid page range: {part!r}')
        first = int(match[1])
        last = int(match[2] or first)
        if not 1 <= first <= last <= count:
            raise ValueError(f'Pages must be within 1-{count}: {part!r}')
        pages.update(range(first, last + 1))
    return sorted(pages)


def normalize(text: str) -> str:
    return ''.join(unicodedata.normalize('NFKC', text).casefold().split())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def open_pdf(path: Path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    if reader.is_encrypted and not reader.decrypt(''):
        raise ValueError('PDF requires a password; provide an accessible local copy.')
    if not reader.pages:
        raise ValueError('PDF contains no pages.')
    return reader


def inspect_pdf(path: Path) -> dict:
    reader = open_pdf(path)
    count = len(reader.pages)
    samples = sorted({1, min(4, count), min(33, count), count})
    return {
        'page_count': count,
        'sha256': sha256(path),
        'text_layer_samples': [
            {'pdf_page': p, 'characters': len((reader.pages[p - 1].extract_text() or '').strip())}
            for p in samples
        ],
        'note': 'Sampled pages only. Verify edition and printed page numbers visually.',
    }


def command_path(name: str) -> str:
    result = shutil.which(name)
    if not result:
        raise ValueError(f'Missing command: {name}. See references/pdf-workflow.md.')
    return result


def run_checked(args: list[str]) -> str:
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise ValueError(f'{Path(args[0]).name} failed: {exc.stderr.strip()[:1200]}') from exc


def prepare_ocr(engine: str, lang: str, temp: Path) -> list[str]:
    command_path('pdftoppm')
    if engine == 'vision':
        if platform.system() != 'Darwin':
            raise ValueError('Vision OCR requires macOS; use --ocr tesseract on other systems.')
        swift = command_path('swiftc')
        executable = temp / 'vision-ocr'
        run_checked([swift, '-module-cache-path', str(temp / 'modules'),
                     str(Path(__file__).with_name('vision_ocr.swift')), '-o', str(executable)])
        return [str(executable)]
    tesseract = command_path('tesseract')
    available = run_checked([tesseract, '--list-langs']).splitlines()
    missing = sorted(set(lang.split('+')) - set(available))
    if missing:
        raise ValueError(f'Missing Tesseract languages: {", ".join(missing)}. Install them locally first.')
    return [tesseract, 'stdout', '-l', lang]


def ocr_page(path: Path, page: int, engine: str, runner: list[str], temp: Path) -> str:
    prefix = temp / f'page-{page}'
    run_checked([command_path('pdftoppm'), '-f', str(page), '-l', str(page),
                 '-singlefile', '-scale-to', '2200', '-png', str(path), str(prefix)])
    image = prefix.with_suffix('.png')
    try:
        if engine == 'vision':
            return run_checked(runner + [str(image)])
        return run_checked([runner[0], str(image)] + runner[1:])
    finally:
        image.unlink(missing_ok=True)


def extract_pdf(path: Path, spec: str, engine: str | None, lang: str) -> dict:
    reader = open_pdf(path)
    count = len(reader.pages)
    pages = parse_pages(spec, count)
    records = []
    with tempfile.TemporaryDirectory(prefix='plant-breeding-') as folder:
        temp = Path(folder)
        runner = None
        for p in pages:
            text = (reader.pages[p - 1].extract_text() or '').strip()
            method = 'text-layer'
            if not text:
                if not engine:
                    raise ValueError(f'PDF page {p} has no extractable text; specify --ocr vision or --ocr tesseract.')
                if runner is None:
                    runner = prepare_ocr(engine, lang, temp)
                text = ocr_page(path, p, engine, runner, temp)
                method = engine
                if not text.strip():
                    raise ValueError(f'OCR produced no text on PDF page {p}; inspect that page visually.')
            records.append({'pdf_page': p, 'method': method, 'text': text})
    return {'schema': 1, 'source_sha256': sha256(path), 'page_count': count,
            'pages': records, 'scope': 'Selected pages only; verify OCR against the original PDF.'}


def search_cache(cache: dict, query: str, limit: int = 5) -> list[dict]:
    if cache.get('schema') != 1 or not isinstance(cache.get('pages'), list):
        raise ValueError('Unsupported reading-cache schema.')
    terms = [normalize(t) for t in query.split() if normalize(t)]
    if not terms:
        raise ValueError('Search query must contain a keyword.')
    if not 1 <= limit <= 100:
        raise ValueError('Limit must be within 1-100.')
    matches = []
    for record in cache['pages']:
        text = record['text']
        if all(t in normalize(text) for t in terms):
            # Keep the original OCR text in excerpts; normalization is only for matching.
            # Find the first matching character position despite inserted whitespace.
            first = terms[0]
            position = 0
            for i in range(len(text)):
                if normalize(text[i:]).startswith(first):
                    position = i
                    break
            matches.append({'pdf_page': record['pdf_page'], 'method': record['method'],
                            'excerpt': text[max(0, position - 60):position + 240]})
            if len(matches) == limit:
                break
    return matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    inspect = sub.add_parser('inspect')
    inspect.add_argument('pdf', type=Path)
    extract = sub.add_parser('extract')
    extract.add_argument('pdf', type=Path)
    extract.add_argument('--pages', required=True)
    extract.add_argument('--ocr', choices=['vision', 'tesseract'])
    extract.add_argument('--lang', default='chi_sim+eng')
    extract.add_argument('--out', type=Path, required=True)
    search = sub.add_parser('search')
    search.add_argument('cache', type=Path)
    search.add_argument('--query', required=True)
    search.add_argument('--limit', type=int, default=5)
    args = parser.parse_args(argv)
    try:
        if args.command == 'inspect':
            result = inspect_pdf(args.pdf)
        elif args.command == 'extract':
            if args.out.resolve() == args.pdf.resolve():
                raise ValueError('Output must not overwrite the source PDF.')
            result = extract_pdf(args.pdf, args.pages, args.ocr, args.lang)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            # Replace atomically only after every selected page was extracted.
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=args.out.parent, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(result, stream, ensure_ascii=False, indent=2)
                stream.write('\n')
            try:
                temporary.replace(args.out)
            finally:
                temporary.unlink(missing_ok=True)
            result = {'saved': str(args.out), 'pages': len(result['pages']),
                      'source_sha256': result['source_sha256']}
        else:
            cache = json.loads(args.cache.read_text(encoding='utf-8'))
            result = {'matches': search_cache(cache, args.query, args.limit),
                      'scope': 'Only the pages in this local cache were searched.',
                      'source_sha256': cache.get('source_sha256')}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, ImportError, KeyError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
