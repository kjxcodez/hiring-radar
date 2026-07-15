"""Verification tests for resume version registry."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.resume.versions import list_resume_versions, resolve_resume_version
from app.cli import resolve_resume_path


class TestResumeVersions(unittest.TestCase):
    def test_list_and_resolve_versions(self):
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            
            # Create a mock resumes folder
            resumes_dir = tmp_path / "resumes"
            resumes_dir.mkdir()
            
            # Write mock files
            (resumes_dir / "default.pdf").write_text("dummy", encoding="utf-8")
            (resumes_dir / "backend.txt").write_text("dummy", encoding="utf-8")
            (resumes_dir / "other.docx").write_text("dummy", encoding="utf-8") # unsupported ext

            # Patch Path.exists and glob/iterdir to simulate this directory
            # Or simpler: patch the internal Path constructor or run within that directory?
            # Actually, let's just patch "app.resume.versions.Path" to return our mock paths!
            with patch("app.resume.versions.Path") as mock_path_cls:
                mock_path_instance = MagicMock()
                mock_path_instance.exists.return_value = True
                
                # mock glob for *.pdf
                pdf_file = MagicMock()
                pdf_file.is_file.return_value = True
                pdf_file.stem = "default"
                pdf_file.name = "default.pdf"
                
                # mock glob for *.txt
                txt_file = MagicMock()
                txt_file.is_file.return_value = True
                txt_file.stem = "backend"
                txt_file.name = "backend.txt"
                
                mock_path_instance.glob.side_effect = lambda ext: [pdf_file] if ext == "*.pdf" else [txt_file]
                
                # resolve checks
                # mock matching path constructions
                mock_path_cls.return_value = mock_path_instance
                
                # 1. list_resume_versions
                versions = list_resume_versions()
                self.assertEqual(versions, ["backend", "default"])

    def test_resolve_resume_version_missing(self):
        # When resumes/ doesn't exist or is empty
        with patch("app.resume.versions.Path") as mock_path_cls:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = False
            mock_path_instance.glob.return_value = []
            mock_path_cls.return_value = mock_path_instance
            
            # mock resolving paths
            mock_pdf = MagicMock()
            mock_pdf.exists.return_value = False
            mock_txt = MagicMock()
            mock_txt.exists.return_value = False
            
            mock_path_instance.__truediv__.side_effect = lambda label: mock_pdf if "pdf" in label else mock_txt
            
            with self.assertRaises(ValueError) as context:
                resolve_resume_version("unknown")
            self.assertIn("Available versions: None found", str(context.exception))

    @patch("app.cli.settings")
    def test_resolve_resume_path_helper(self, mock_settings):
        mock_settings.resume_path = Path("resumes/default.pdf")
        
        # 1. No arg falls back to settings.resume_path
        self.assertEqual(resolve_resume_path(None), Path("resumes/default.pdf"))

        # 2. Existing path is returned directly
        with patch("app.cli.Path") as mock_path_cls:
            mock_p = MagicMock()
            mock_p.exists.return_value = True
            mock_p.is_file.return_value = True
            mock_path_cls.return_value = mock_p
            
            self.assertEqual(resolve_resume_path("custom/my_resume.txt"), mock_p)


if import_helper := True:
    from unittest.mock import MagicMock
