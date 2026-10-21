"""R-W2-007 — the seven real capabilities: every field derived, evidence cited.

Acceptance (ROADMAP): «كل قدرة باختبار تكامل حقيقي؛ لا نتيجة إيجابية بلا فحص».
لكل قدرة: اختبار عبر المسار الحقيقي (مهمة تُحل بالاسم، أو قرص حقيقي)، وحالة إيجابية،
وحالة سلبية، ومدخل ناقص/معطوب. النتائج تثبت الدليل (ملف/سطر/عبارة/بسط-مقام)، لا
مجرد وجود المفاتيح.

فحص OSV ثلاث طبقات: دالة محقونة (حتمية)، وطبقة HTTP فعلية بمخدم محلي، واختبار حي
مرجعي يُتخطى بلا شبكة (لا يُعد نجاحاً مثبتاً — بالتصميم).
"""
import http.server
import json
import os
import re
import shutil
import socket
import subprocess
import threading

import pytest

from agos.kernel.capabilities import (
    ConfigurationAnalysisCapability,
    DocumentationAnalysisCapability,
    EngineeringKnowledgeExtractionCapability,
    InfrastructureAnalysisCapability,
    LicenseAnalysisCapability,
    RepositoryDNAGenerationCapability,
    SecurityScanCapability,
)
from agos.kernel.capabilities.foundation_extra import (
    osv_query_batch,
    pinned_version,
    spdx_license_of,
)


def _git_repo(path, files, default_branch="main"):
    """A real local git repo (needed for the url flow; plain dirs work for repo_path)."""
    path.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        p = path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "PATH": os.environ["PATH"]}
    for cmd in (["git", "init", "-q", "-b", default_branch],
                ["git", "remote", "add", "origin", "https://github.com/t/ref.git"],
                ["git", "add", "-A", "-f"], ["git", "commit", "-qm", "init"]):
        subprocess.run(cmd, cwd=path, check=True, env=env, capture_output=True)
    return path


MIT_TEXT = ("MIT License\n\nCopyright (c) 2026 t\n\n"
            "Permission is hereby granted, free of charge, to any person obtaining a copy "
            "of this software and associated documentation files (the \"Software\"), to deal\n"
            "in the Software without restriction, including without limitation the rights\n")
APACHE_TEXT = ("Apache License\nVersion 2.0, January 2004\n\n"
               "1. Definitions.\n")


def _no_osv(query):
    """Injected OSV: deterministic — no network in unit tests."""
    return [{"vulns": []} for _ in query]


def _osv_raising(query):
    raise OSError("network down")


# ===========================================================================
# SecurityScan
# ===========================================================================
class TestSecurityScan:
    def test_secret_in_env_found_with_redacted_evidence(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "print('hi')\n",
            ".env": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n",
        })
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        assert out["secrets_found"] == 1
        finding = out["secrets"][0]
        assert finding["file"] == ".env"
        assert finding["line"] == 1
        assert finding["rule"] == "aws-access-key"
        # الدليل منقّح: لا يُعاد السر الخام في أي مكان من النتيجة
        assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(out)
        assert finding["evidence"].startswith("AKIA")
        assert out["risk_level"] == "high"
        # لا اعتماديات في هذا المستودع — فحص OSV معلن كمتخطى لا كناجح
        assert out["osv_status"] == "skipped_no_pins"

    def test_clean_repo_with_completed_checks_is_low(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "print('hi')\n", "requirements.txt": "flask==1.0\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        assert out["secrets_found"] == 0
        assert out["vulnerabilities"] == []
        assert out["risk_level"] == "low"   # وحدها الفحوص المكتملة النظيفة تستحقها

    def test_osv_failure_is_never_low(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "requirements.txt": "flask==1.0\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _osv_raising})
        assert out["osv_status"] == "failed"
        assert "network down" in out["osv_error"]
        assert out["risk_level"] == "medium"   # فحص تعثر ≠ آمن

    def test_range_specs_are_unresolved_not_checked(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "requirements.txt": "flask>=1.0\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        assert out["osv_status"] == "skipped_no_pins"
        assert out["unresolved_dependencies"] == [
            {"name": "flask", "specifier": ">=1.0"}]
        assert out["risk_level"] == "medium"

    def test_env_example_is_scanned_but_placeholders_are_not(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "x\n",
            ".env.example": "API_KEY=abcdefghijklmnop\nDB_URL=${DATABASE_URL}\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        rules = {f["rule"] for f in out["secrets"]}
        assert "generic-secret" in rules          # لا استثناء شامل لـ.env.example
        flagged = [f for f in out["secrets"] if f["rule"] == "generic-secret"]
        assert len(flagged) == 1                  # ${DATABASE_URL} placeholder لم يُحسب

    def test_private_key_block_detected(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "deploy.key": "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        assert any(f["rule"] == "private-key" for f in out["secrets"])

    def test_malformed_input_raises(self):
        with pytest.raises(ValueError):
            SecurityScanCapability().execute({})

    def test_pinned_version_parsing(self):
        assert pinned_version("==1.2.3", "pypi") == "1.2.3"
        assert pinned_version("1.2.3", "npm") == "1.2.3"
        assert pinned_version("v1.9.1", "go") == "1.9.1"
        assert pinned_version("5.0", "rubygems") == "5.0"
        # وعي بالنظام البيئي: في pypi الاسم المجرد ليس تثبيتاً
        # وفي Cargo.toml الـ 1.2.3 تعني مطاوقاً ^1.2.3 لا تثبيتاً
        assert pinned_version("flask", "pypi") is None
        assert pinned_version("1.2.3", "cargo") is None
        assert pinned_version(">=2.0", "pypi") is None
        assert pinned_version("^18.2.0", "npm") is None
        assert pinned_version("${spring.version}", "maven") is None
        assert pinned_version("", "npm") is None

    def test_short_osv_response_is_partial_not_clean(self, tmp_path):
        # استجابة أقصر من الاستعلامات: فحص جزئي يُعلن ولا يبدو نظيفاً
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "requirements.txt": "flask==1.0\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": lambda queries: []})
        assert out["osv_status"] == "partial"
        assert out["risk_level"] == "medium"

    def test_unreadable_files_make_scan_partial(self):
        out = SecurityScanCapability().execute({
            "files": {"requirements.txt": "flask==1.0\n", "blob.bin": None},
            "osv_query": _no_osv})
        assert out["unreadable_files"] == 1
        assert out["risk_level"] == "medium"   # فحص جزئي لا «آمنة»

    def test_manifest_parse_errors_make_scan_partial(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "x\n", "pyproject.toml": "[project\nname = broken\n"})
        out = SecurityScanCapability().execute(
            {"url": f"file://{repo}", "osv_query": _no_osv})
        assert out["manifest_parse_errors"]
        assert out["risk_level"] == "medium"

    def test_version_attribute_kept_on_all_seven(self):
        for cap in (SecurityScanCapability, LicenseAnalysisCapability,
                    DocumentationAnalysisCapability, ConfigurationAnalysisCapability,
                    InfrastructureAnalysisCapability, RepositoryDNAGenerationCapability,
                    EngineeringKnowledgeExtractionCapability):
            assert cap.version == "1.0.0"

    def test_old_contract_list_of_files_accepted(self):
        # عقد قديم: قائمة عقد ملفات مباشرة (لا قاموس)
        nodes = [{"path": "main.py", "content": "x\n", "is_dir": False, "size": 2}]
        out = SecurityScanCapability().execute({"files": nodes, "osv_query": _no_osv})
        assert out["scanned_files"] == 1

    def test_snapshot_dict_with_files_mapping(self):
        # {"snapshot": {"files": {path: content}}} لا يتحول لملفات مساراتها فارغة
        out = SecurityScanCapability().execute(
            {"snapshot": {"files": {"main.py": "x\n"}}, "osv_query": _no_osv})
        assert out["scanned_files"] == 1

    def test_repository_snapshot_object_direct(self, tmp_path):
        from providers import LocalRepositoryProvider
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
        snap = LocalRepositoryProvider().Read(str(repo))
        out = SecurityScanCapability().execute(snap)   # اللقطة نفسها — لا غلاف
        assert out["scanned_files"] >= 1


# ===========================================================================
# OSV layers: injected / local HTTP / live (gated)
# ===========================================================================
class TestOsvLayers:
    def test_osv_over_local_http_server(self):
        # طبقة HTTP فعلية: مخدم محلي يرد استجابة querybatch حقيقية الشكل
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.dumps({"results": [
                    {"vulns": [{"id": "GHSA-xxxx", "summary": "RCE in old lib"}]},
                    {}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            queries = [{"package": {"name": "flask", "ecosystem": "PyPI"}, "version": "0.12"},
                       {"package": {"name": "requests", "ecosystem": "PyPI"}, "version": "2.19.1"}]
            results = osv_query_batch(
                queries, endpoint=f"http://127.0.0.1:{port}/v1/querybatch")
            assert results[0]["vulns"][0]["id"] == "GHSA-xxxx"
            assert results[1] == {}
        finally:
            server.shutdown()

    def test_osv_live_reference_version(self):
        # اختبار حي مرجعي: requests 2.19.1 معروف بثغرة CVE-2018-18074.
        # يُتخطى بلا شبكة (بالتصميم) — التخطي ليس نجاحاً مثبتاً.
        try:
            results = osv_query_batch(
                [{"package": {"name": "requests", "ecosystem": "PyPI"},
                  "version": "2.19.1"}], timeout=15)
        except OSError as exc:
            pytest.skip(f"network/GitHub unreachable: {exc}")
        ids = [v.get("id") for v in results[0].get("vulns", [])]
        # المعرف المرجعي تحديداً: GHSA-x84v-xcm2-53pg هو بالضبط CVE-2018-18074
        # (تسريب الاعتماديات في requests < 2.20.0) — لا أي معرف غير فارغ
        assert "GHSA-x84v-xcm2-53pg" in ids, ids


# ===========================================================================
# License
# ===========================================================================
class TestLicense:
    def test_mit_detected_from_text_with_evidence(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "LICENSE": MIT_TEXT})
        out = LicenseAnalysisCapability().execute({"url": f"file://{repo}"})
        assert out["license"] == "MIT"
        assert out["license_file"] == "LICENSE"
        assert "Permission is hereby granted" in out["evidence"]

    def test_declared_vs_detected_mismatch_reported(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "package.json": json.dumps({"name": "x", "license": "MIT"}),
            "LICENSE": APACHE_TEXT})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["declared_license"] == "MIT"
        assert out["declaration_file"] == "package.json"
        assert out["license"] == "Apache-2.0"
        assert out["mismatch"] is True

    def test_readme_mention_is_not_a_license(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "README.md": "# Project\nLicensed under the MIT license.\n", "main.py": "x\n"})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["license"] == "unknown"
        assert out["license_file"] is None

    def test_compatibility_is_never_assumed(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"LICENSE": MIT_TEXT})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["compatible"] is None
        assert out["dependency_licenses_status"] == "not_collected"

    def test_spdx_unit_table(self):
        assert spdx_license_of("SPDX-License-Identifier: MIT\nstuff")[0] == "MIT"
        assert spdx_license_of(APACHE_TEXT)[0] == "Apache-2.0"
        assert spdx_license_of("random text")[0] == "unknown"

    def test_bsd_distinguished_by_clause_not_line_wrap(self, tmp_path):
        # نفس المقدمة بلا بند المنع ← BSD-2؛ وبنود البنود مع بند المنع ← BSD-3
        intro = "Redistribution and use in source and binary forms, with or without modification"
        assert spdx_license_of(intro)[0] == "BSD-2-Clause"
        assert spdx_license_of(
            intro + "\n\n" + "Neither the name of the copyright holder nor the names of its "
            "contributors may be used to endorse")[0] == "BSD-3-Clause"
        repo = _git_repo(tmp_path / "src", {"LICENSE": intro + "\n", "main.py": "x\n"})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["license"] == "BSD-2-Clause"

    def test_gpl_or_later_by_evidence(self):
        base = "GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n"
        assert spdx_license_of(base)[0] == "GPL-3.0-only"
        assert spdx_license_of(
            base + "...or (at your option) any later version.\n")[0] == "GPL-3.0-or-later"

    def test_unknown_copying_does_not_shadow_known_license(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "COPYING": "Some custom proprietary text\n",
            "LICENSE": MIT_TEXT, "main.py": "x\n"})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["license"] == "MIT"          # المفضّل: المعروف لا الأول ترتيباً
        assert sorted(out["license_candidates"]) == ["COPYING", "LICENSE"]

    def test_package_json_list_and_tool_section_not_declared(self, tmp_path):
        # JSON صالح لكنه قائمة ← ليس كائن مشروع؛ وlicense داخل [tool.*] ليس إعلان المشروع
        repo = _git_repo(tmp_path / "src", {
            "package.json": "[1, 2, 3]",
            "pyproject.toml": "[tool.poetry]\nlicense = 'Proprietary'\n",
            "main.py": "x\n"})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["declared_license"] is None

    def test_pyproject_project_license_table(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "pyproject.toml": "[project]\nname = 'x'\nlicense = {text = 'BSD-3-Clause'}\n",
            "main.py": "x\n"})
        out = LicenseAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["declared_license"] == "BSD-3-Clause"
        assert out["declaration_file"] == "pyproject.toml"


# ===========================================================================
# Documentation
# ===========================================================================
class TestDocumentation:
    def test_docstring_coverage_measured_with_counts(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "a.py": 'def documented():\n    """Doc."""\n',
            "b.py": "def bare():\n    pass\n"})
        out = DocumentationAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["doc_coverage_counts"] == {"documented": 1, "total": 2}
        assert out["doc_coverage"] == 0.5
        assert out["doc_coverage_scope"] == "python-public-docstrings"

    def test_missing_docs_listed_from_real_absence(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n"})
        out = DocumentationAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["missing_docs"] == ["README", "LICENSE", "CONTRIBUTING", "CHANGELOG"]
        assert out["has_readme"] is False

    def test_syntax_error_not_counted_and_no_crash(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"broken.py": "def (:\n"})
        out = DocumentationAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["doc_coverage_counts"] == {"documented": 0, "total": 0}
        assert out["python_parse_errors"] == ["broken.py"]   # معلنة لا مطمسة

    def test_scope_nested_and_private_not_counted(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"a.py": (
            '"""Mod."""\n\n'
            'def outer():\n'
            '    def inner():\n'          # تفصيل تنفيذي داخل دالة — لا يُحصى
            '        """doc"""\n'
            '        pass\n\n'
            'class C:\n'
            '    def _private(self):\n'   # خاص — لا يُحصى
            '        pass\n\n'
            '    def public(self):\n'
            '        """doc"""\n')})
        out = DocumentationAnalysisCapability().execute({"repo_path": str(repo)})
        # النطاق المعلن: outer وC وpublic فقط (inner تفصيل تنفيذي و_private خاص)
        assert out["doc_coverage_counts"] == {"documented": 1, "total": 3}


# ===========================================================================
# Configuration
# ===========================================================================
class TestConfiguration:
    def test_environments_by_full_word_only(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "x\n",
            "settings.production.yaml": "a: 1\n",
            "device.config.json": json.dumps({"ok": True})})
        out = ConfigurationAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["environments"] == ["production"]   # device ليست بيئة dev
        assert "settings.production.yaml" in out["config_files"]
        assert out["issues"] == []

    def test_invalid_json_reported_with_file(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "x\n", "config.json": "{not valid json"})
        out = ConfigurationAnalysisCapability().execute({"repo_path": str(repo)})
        assert len(out["issues"]) == 1
        assert out["issues"][0]["file"] == "config.json"
        assert "invalid JSON" in out["issues"][0]["issue"]

    def test_committed_env_without_example_is_an_issue(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", ".env": "A=1\n"})
        out = ConfigurationAnalysisCapability().execute({"repo_path": str(repo)})
        assert any(i["file"] == ".env" for i in out["issues"])

    def test_env_via_files_input_is_an_issue_too(self):
        # وحدة المدخلات: ملف .env معطى عبر files يُعامل كالموجود على القرص
        out = ConfigurationAnalysisCapability().execute(
            {"files": {"main.py": "x\n", ".env": "A=1\n"}})
        assert any(i["file"] == ".env" for i in out["issues"])

    def test_empty_json_is_read_and_reported_invalid(self, tmp_path):
        # المحتوى الفارغ مقروء — يُفحص ويُرفض، لا يُتخطى
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "config.json": ""})
        out = ConfigurationAnalysisCapability().execute({"repo_path": str(repo)})
        assert any(i["file"] == "config.json" for i in out["issues"])


# ===========================================================================
# Infrastructure
# ===========================================================================
class TestInfrastructure:
    def test_docker_k8s_terraform_evidence(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "x\n",
            "Dockerfile": "FROM python:3.12\n",
            "k8s.yaml": "apiVersion: apps/v1\nkind: Deployment\n",
            "main.tf": 'provider "aws" {\n  region = "us-east-1"\n}\n'})
        out = InfrastructureAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["has_docker"] and "Dockerfile" in out["docker_evidence"]
        assert out["has_kubernetes"] and "k8s.yaml" in out["kubernetes_evidence"]
        assert out["has_terraform"] and "main.tf" in out["terraform_evidence"]
        assert out["cloud_providers"] == ["aws"]

    def test_cloud_sdk_is_dependency_evidence_not_deployed_infra(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "requirements.txt": "boto3\n"})
        out = InfrastructureAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["cloud_providers"] == ["aws"]
        assert out["cloud_evidence"]["aws"]["sdk_dependencies"] == ["boto3"]
        assert out["cloud_evidence_type"] == "sdk-dependency-or-terraform-block"
        assert out["has_docker"] is False

    def test_yaml_without_k8s_shape_is_not_kubernetes(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {"docker-compose.yml": "version: '3'\nservices: {}\n"})
        out = InfrastructureAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["has_kubernetes"] is False
        assert out["has_docker"] is True

    def test_sdk_mention_in_readme_is_not_dependency_evidence(self, tmp_path):
        # ذكر boto3 في README ليس دليل اعتماد — الاعتماد الفعلي في ملفات الاعتماديات
        repo = _git_repo(tmp_path / "src", {
            "README.md": "# Uses boto3 for AWS\n", "main.py": "x\n"})
        out = InfrastructureAnalysisCapability().execute({"repo_path": str(repo)})
        assert out["cloud_providers"] == []

    def test_terraform_provider_names_map_correctly(self, tmp_path):
        # gcp عبر اسم TF الفعلي (google) وazure عبر (azurerm) — لا الأسماء الشائعة
        repo = _git_repo(tmp_path / "src", {
            "main.tf": 'provider "google" {\n  region = "europe"\n}\n',
            "app.tf": 'provider "azurerm" {\n  features {}\n}\n'})
        out = InfrastructureAnalysisCapability().execute({"repo_path": str(repo)})
        assert "gcp" in out["cloud_providers"]
        assert "azure" in out["cloud_providers"]


# ===========================================================================
# DNA
# ===========================================================================
class TestDNA:
    def test_dna_from_real_detection(self, tmp_path):
        repo = _git_repo(tmp_path / "src", {
            "main.py": "import flask\n", "requirements.txt": "flask==1.0\n"})
        out = RepositoryDNAGenerationCapability().execute({"repo_path": str(repo)})
        assert out["languages"] == ["Python"]
        assert "Flask" in out["frameworks"]
        assert "pip" in out["package_managers"]
        assert re.fullmatch(r"[0-9a-f]{64}", out["fingerprint"])
        assert out["fingerprint_basis"] == "sorted-facts-sha256"

    def test_fingerprint_stable_under_file_order(self):
        files_a = {"a.py": "x\n", "b.js": "y\n", "requirements.txt": "flask==1.0\n"}
        files_b = {"requirements.txt": "flask==1.0\n", "b.js": "y\n", "a.py": "x\n"}
        out_a = RepositoryDNAGenerationCapability().execute({"files": files_a})
        out_b = RepositoryDNAGenerationCapability().execute({"files": files_b})
        assert out_a["fingerprint"] == out_b["fingerprint"]
        # متعدد اللغات: البصمة مستقلة للترتيب (الترتيب يُطبّع في المصدر)

    def test_primary_language_explicit_and_tie_break(self):
        # لغتان متساويتان أسطراً مختلفتان ملفات: الرئيسية هي الأكثر ملفات —
        # وليست بالضرورة أول القائمة المرتبة بالأسطر فالاسم
        files = {"app.py": "x\nx\n", "one.js": "x\n", "two.js": "x\n"}
        out = RepositoryDNAGenerationCapability().execute({"files": files})
        assert out["primary_language"] == "JavaScript"   # ملفان مقابل ملف
        assert out["languages"] == ["JavaScript", "Python"]


# ===========================================================================
# KnowledgeExtraction
# ===========================================================================
class TestKnowledgeExtraction:
    def test_findings_cite_sources_and_failures_pass_through(self):
        out = EngineeringKnowledgeExtractionCapability().execute({
            "analysis_results": [
                {"capability": "SecurityScan", "secrets_found": 1,
                 "secrets": [{"file": ".env", "line": 1}],
                 "vulnerabilities": [], "osv_status": "failed", "risk_level": "medium"},
                {"capability": "LicenseAnalysis", "license": "unknown"},
            ]})
        assert out["key_findings"][0]["source"] == "SecurityScan.secrets_found"
        assert any("rotate/remove" in r["recommendation"]
                   for r in out["recommendations"])
        assert any("OSV check failed" in g for g in out["gaps"])   # الفشل يُمرَّر
        assert "risk medium" in out["summary"]

    def test_missing_capability_result_is_a_gap_not_calm(self):
        out = EngineeringKnowledgeExtractionCapability().execute({
            "analysis_results": [{"capability": "LicenseAnalysis", "license": "MIT"}]})
        assert any("SecurityScan result missing" in g for g in out["gaps"])

    def test_bad_input_raises(self):
        with pytest.raises(ValueError):
            EngineeringKnowledgeExtractionCapability().execute({"analysis_results": "nope"})

    def test_old_contract_bare_list_accepted(self):
        # عقد قديم: القائمة مباشرة بلا غلاف قاموسي
        out = EngineeringKnowledgeExtractionCapability().execute([
            {"capability": "LicenseAnalysis", "license": "MIT"}])
        assert out["key_findings"] == []

    def test_extraction_from_real_outputs_of_all_six(self, tmp_path):
        # تكامل حقيقي: مخرجات القدرات الست فعلياً (لا نتائج مصطنعة) تغذي الاستخراج
        repo = _git_repo(tmp_path / "src", {
            "main.py": "import flask\n",
            "requirements.txt": "flask==0.12\n",
            "LICENSE": MIT_TEXT,
            ".env": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\n"})
        inputs = {"repo_path": str(repo), "osv_query": _no_osv}
        results = [
            SecurityScanCapability().execute(dict(inputs)),
            LicenseAnalysisCapability().execute({"repo_path": str(repo)}),
            DocumentationAnalysisCapability().execute({"repo_path": str(repo)}),
            ConfigurationAnalysisCapability().execute({"repo_path": str(repo)}),
            InfrastructureAnalysisCapability().execute({"repo_path": str(repo)}),
            RepositoryDNAGenerationCapability().execute({"repo_path": str(repo)}),
        ]
        out = EngineeringKnowledgeExtractionCapability().execute(results)
        sources = {f["source"] for f in out["key_findings"]}
        assert any(s.startswith("SecurityScan") for s in sources)   # السر الحقيقي
        assert out["key_findings"][0]["source"] == "SecurityScan.secrets_found"
        assert any("Python" in out["summary"] for _ in [0])       # DNA حقيقي في الملخص
        recs = " ".join(r["recommendation"] for r in out["recommendations"])
        assert ".env" in recs                                        # توصية مدققة


# ===========================================================================
# Missions — integration through the real runtime (resolution by name)
# ===========================================================================
class TestMissions:
    def test_security_scan_mission_resolves_and_executes(self, tmp_path):
        from agos.kernel import agos_runtime

        repo = _git_repo(tmp_path / "src", {"main.py": "x\n", "requirements.txt": "flask==1.0\n"})
        k = agos_runtime.boot()
        outcome = k.run({
            "name": "Scan", "description": "scan",
            "capability": "SecurityScan",
            "parameters": {"url": f"file://{repo}", "osv_query": _no_osv},
        })
        assert outcome.state.value == "completed"
        assert outcome.result["capability"] == "SecurityScan"
        events = k.event_bus.get_events(outcome.mission_id)
        selected = [e.data for e in events if e.type.value == "capability_selected"]
        assert selected and selected[0]["capability"] == "SecurityScan"

    def test_license_mission_via_repo_path(self, tmp_path):
        from agos.kernel import agos_runtime

        repo = _git_repo(tmp_path / "src", {"LICENSE": MIT_TEXT, "main.py": "x\n"})
        k = agos_runtime.boot()
        outcome = k.run({
            "name": "License", "description": "license",
            "capability": "LicenseAnalysis",
            "parameters": {"repo_path": str(repo)},
        })
        assert outcome.state.value == "completed"
        assert outcome.result["license"] == "MIT"

    def test_failed_scan_mission_is_reported_not_raised(self, tmp_path):
        from agos.kernel import agos_runtime

        k = agos_runtime.boot()
        outcome = k.run({
            "name": "Bad", "description": "bad",
            "capability": "SecurityScan",
            "parameters": {"url": "http://evil.example.com/x"},   # مرفوض بقائمة السماح
        })
        assert outcome.state.value == "failed"
        assert outcome.error
