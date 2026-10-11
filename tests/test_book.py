"""Behavior checks use invented text and tiny original in-memory PDF fixtures."""
import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/study-molecular-plant-breeding/scripts/book.py'
spec = importlib.util.spec_from_file_location('book', SCRIPT)
book = importlib.util.module_from_spec(spec)
spec.loader.exec_module(book)


def write_pdf(path, text=None, pages=1):
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=200, height=200)
        if text:
            font = DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                     NameObject('/Subtype'): NameObject('/Type1'),
                                     NameObject('/BaseFont'): NameObject('/Helvetica')})
            page[NameObject('/Resources')] = DictionaryObject({
                NameObject('/Font'): DictionaryObject({NameObject('/F1'): writer._add_object(font)})})
            content = DecodedStreamObject()
            content.set_data(f'BT /F1 12 Tf 10 100 Td ({text}) Tj ET'.encode('ascii'))
            page[NameObject('/Contents')] = writer._add_object(content)
    with path.open('wb') as stream:
        writer.write(stream)


class Pages(unittest.TestCase):
    def test_ranges_are_physical_sorted_and_unique(self):
        self.assertEqual(book.parse_pages('4, 1-3,2', 4), [1,2,3,4])

    def test_invalid_ranges_fail(self):
        for spec in ['0','5','3-1','1-8','x','','1,','-1','1.5']:
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                book.parse_pages(spec, 4)

    def test_first_and_last_page(self):
        self.assertEqual(book.parse_pages('1,770',770), [1,770])


class Search(unittest.TestCase):
    def setUp(self):
        self.cache = {'schema':1,'pages':[
            {'pdf_page':7,'method':'vision','text':'虚构例子：前 景选择和背 景选择'},
            {'pdf_page':8,'method':'text-layer','text':'QTL and marker comparison'},
            {'pdf_page':9,'method':'vision','text':'只有前景'}]}

    def test_chinese_spacing_and_all_terms(self):
        self.assertEqual([r['pdf_page'] for r in book.search_cache(self.cache,'前景 背景')],[7])

    def test_casefold_and_fullwidth(self):
        self.assertEqual(book.search_cache(self.cache,'ＱＴＬ')[0]['pdf_page'],8)

    def test_no_match_is_empty(self):
        self.assertEqual(book.search_cache(self.cache,'不存在'),[])

    def test_limit(self):
        self.assertEqual(len(book.search_cache(self.cache,'前景',1)),1)

    def test_empty_query_fails(self):
        with self.assertRaises(ValueError): book.search_cache(self.cache,'  ')

    def test_invalid_limits_fail(self):
        for limit in [0,-1,101]:
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                book.search_cache(self.cache,'前景',limit)

    def test_unknown_schema_fails(self):
        with self.assertRaises(ValueError): book.search_cache({'schema':2,'pages':[]},'x')

    def test_excerpts_preserve_original_text(self):
        self.assertIn('前 景',book.search_cache(self.cache,'前景')[0]['excerpt'])


class PdfAndCli(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.pdf = self.root/'original-test.pdf'

    def test_inspect_blank_pages_and_source_hash(self):
        write_pdf(self.pdf,pages=3)
        result = book.inspect_pdf(self.pdf)
        self.assertEqual(result['page_count'],3)
        self.assertEqual(len(result['sha256']),64)
        self.assertTrue(all(p['characters']==0 for p in result['text_layer_samples']))

    def test_text_layer_extract_preserves_page_number(self):
        write_pdf(self.pdf,'Original invented study question',pages=2)
        result = book.extract_pdf(self.pdf,'2',None,'eng')
        self.assertEqual(result['pages'][0]['pdf_page'],2)
        self.assertEqual(result['pages'][0]['method'],'text-layer')
        self.assertIn('invented',result['pages'][0]['text'])
        self.assertEqual(result['source_sha256'],book.sha256(self.pdf))

    def test_blank_page_requires_ocr(self):
        write_pdf(self.pdf)
        with self.assertRaisesRegex(ValueError,'no extractable text'):
            book.extract_pdf(self.pdf,'1',None,'eng')

    @patch.object(book,'ocr_page',return_value='原创识别测试')
    @patch.object(book,'prepare_ocr',return_value=['mock'])
    def test_ocr_fallback_and_provenance(self,prepare,ocr):
        write_pdf(self.pdf)
        result = book.extract_pdf(self.pdf,'1','vision','eng')
        self.assertEqual(result['pages'][0],{'pdf_page':1,'method':'vision','text':'原创识别测试'})
        prepare.assert_called_once()

    @patch.object(book,'ocr_page',return_value='')
    @patch.object(book,'prepare_ocr',return_value=['mock'])
    def test_empty_ocr_fails(self,*mocks):
        write_pdf(self.pdf)
        with self.assertRaisesRegex(ValueError,'no text'):
            book.extract_pdf(self.pdf,'1','vision','eng')

    def test_cli_atomic_output_and_search(self):
        write_pdf(self.pdf,'Invented QTL question')
        out=self.root/'cache'/'index.json'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(book.main(['extract',str(self.pdf),'--pages','1','--out',str(out)]),0)
        cache=json.loads(out.read_text())
        self.assertEqual(cache['pages'][0]['pdf_page'],1)
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code=book.main(['search',str(out),'--query','qtl'])
        self.assertEqual(code,0)
        self.assertEqual(json.loads(stdout.getvalue())['matches'][0]['pdf_page'],1)

    def test_failed_extract_preserves_existing_output(self):
        write_pdf(self.pdf)
        out=self.root/'index.json';out.write_text('original')
        with contextlib.redirect_stderr(io.StringIO()):
            code=book.main(['extract',str(self.pdf),'--pages','1','--out',str(out)])
        self.assertEqual(code,2)
        self.assertEqual(out.read_text(),'original')

    def test_source_overwrite_rejected(self):
        write_pdf(self.pdf,'Source content')
        digest=book.sha256(self.pdf)
        with contextlib.redirect_stderr(io.StringIO()):
            code=book.main(['extract',str(self.pdf),'--pages','1','--out',str(self.pdf)])
        self.assertEqual(code,2)
        self.assertEqual(book.sha256(self.pdf),digest)

    @patch.object(book.shutil,'which',return_value='/mock/tool')
    @patch.object(book,'run_checked',return_value='List of languages:\neng\n')
    def test_missing_tesseract_language_reported(self,*mocks):
        with self.assertRaisesRegex(ValueError,'chi_sim'):
            book.prepare_ocr('tesseract','chi_sim+eng',self.root)

    @patch.object(book.shutil,'which',return_value='/mock/tool')
    @patch.object(book.platform,'system',return_value='Linux')
    def test_vision_requires_macos(self,*mocks):
        with self.assertRaisesRegex(ValueError,'macOS'):
            book.prepare_ocr('vision','eng',self.root)

    def test_hash_changes_when_source_changes(self):
        self.pdf.write_bytes(b'first');first=book.sha256(self.pdf)
        self.pdf.write_bytes(b'second');self.assertNotEqual(first,book.sha256(self.pdf))


if __name__=='__main__': unittest.main()
