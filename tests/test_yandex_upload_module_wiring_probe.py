"""Tests for the source-free V9 Yandex upload module-wiring probe."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import unittest


_ROOT = Path(__file__).resolve().parents[1]
_TOOLS = _ROOT / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

_TOOL = _TOOLS / "yandex_upload_module_wiring_probe.py"
_SPEC = importlib.util.spec_from_file_location("yandex_upload_module_wiring_probe", _TOOL)
assert _SPEC is not None and _SPEC.loader is not None
probe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(probe)


class YandexUploadModuleWiringProbeTests(unittest.TestCase):
    def test_resolves_export_import_and_constructor_without_secret_values(self) -> None:
        source = (
            '(self.webpackChunk=self.webpackChunk||[]).push([[1],{'
            '101:(e,t,n)=>{'
            'n.d(t,{UgcUploadHttpClient:()=>u});'
            'u=class extends BaseResourceHttpClient{constructor(t){'
            'super({prefixUrl:t.prefixUrl,headers:createSessionRequestHeaders(t),'
            'clientRemoteType:t.clientRemoteType})}}},'
            '202:(e,t,n)=>{'
            'var r=n(101);'
            'const cfg={customApiPrefixUrl:getApiPrefixUrl(runtime),'
            'customApiToken:SUPER_SECRET_TOKEN,clientRemoteType:YandexMusicDesktopApp};'
            'const client=new r.UgcUploadHttpClient(createHttpOptions({'
            'prefixUrl:cfg.customApiPrefixUrl,'
            'headers:createRequestHeaders(cfg.customApiToken),'
            'clientRemoteType:cfg.clientRemoteType}))'
            '}}]);'
        )

        modules = probe._extract_modules(source)  # noqa: SLF001
        self.assertEqual({item["module_id"] for item in modules}, {"101", "202"})

        infos = [probe._module_info("synthetic.js", item, probe.DEFAULT_ANCHORS) for item in modules]  # noqa: SLF001
        by_id = {item["module_id"]: item for item in infos}
        encoded = json.dumps(infos, ensure_ascii=False)

        self.assertIn(
            {"name": "UgcUploadHttpClient", "symbol": "u"},
            by_id["101"]["named_exports"],
        )
        self.assertIn(
            {"local": "r", "source_module_id": "101"},
            by_id["202"]["imports"],
        )
        self.assertTrue(
            any(
                item.get("export_name") == "UgcUploadHttpClient"
                and item.get("source_module_id") == "101"
                for item in by_id["202"]["constructor_uses"]
            )
        )
        self.assertTrue(
            any(
                item.get("export_name") == "UgcUploadHttpClient"
                and item.get("extends") == "BaseResourceHttpClient"
                for item in by_id["101"]["class_relations"]
            )
        )
        self.assertNotIn("SUPER_SECRET_TOKEN", encoded)

        edges = probe._resolved_edges(infos)  # noqa: SLF001
        self.assertIn(
            {
                "from_module_id": "202",
                "to_module_id": "101",
                "export_name": "UgcUploadHttpClient",
                "relation": "constructor-use",
            },
            edges,
        )

    def test_function_style_webpack_module_is_detected(self) -> None:
        source = '77:function(e,t,n){n.d(t,{ResourceHttpClient:function(){return a}});a=class{}}'
        modules = probe._extract_modules(source)  # noqa: SLF001
        self.assertEqual(len(modules), 1)
        info = probe._module_info("synthetic.js", modules[0], probe.DEFAULT_ANCHORS)  # noqa: SLF001
        self.assertIn({"name": "ResourceHttpClient", "symbol": "a"}, info["named_exports"])

    def test_constructor_arguments_are_structural_only(self) -> None:
        source = (
            '202:(e,t,n)=>{var r=n(101);'
            'new r.UgcUploadHttpClient(createHttpOptions({'
            'prefixUrl:cfg.customApiPrefixUrl,customApiToken:VERY_PRIVATE_TOKEN}))}'
        )
        module = probe._extract_modules(source)[0]  # noqa: SLF001
        info = probe._module_info("synthetic.js", module, probe.DEFAULT_ANCHORS)  # noqa: SLF001
        encoded = json.dumps(info, ensure_ascii=False)
        self.assertNotIn("VERY_PRIVATE_TOKEN", encoded)
        self.assertTrue(info["constructor_uses"])


if __name__ == "__main__":
    unittest.main()
