# Copyright (C) 2025 - Ported from Pixelle-Video (Apache 2.0)
"""HTML Frame Generator - Render HTML templates to images using Playwright."""

import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional


class HTMLFrameGenerator:
    """Render HTML templates to frame images with Playwright."""

    _browser = None
    _playwright = None

    def __init__(self, template_path: str):
        self.template_path = template_path
        self.template = self._load_template(template_path)
        self.width, self.height = self._parse_template_size(template_path)

    def _load_template(self, template_path: str) -> str:
        path = Path(template_path)
        if not path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _parse_template_size(self, template_path: str):
        """Parse size from path like templates/1080x1920/file.html (mobile portrait)"""
        path = Path(template_path)
        dir_name = path.parent.name
        if "x" in dir_name:
            parts = dir_name.split("x")
            return int(parts[0]), int(parts[1])
        # Default: 9:16 portrait for mobile
        return 1080, 1920

    def _replace_parameters(self, html: str, values: Dict[str, Any]) -> str:
        pattern = r"\{\{([a-zA-Z_][a-zA-Z0-9_]*)(?::([a-z]+))?(?:=([^}]+))?\}\}"
        def replacer(match):
            param_name = match.group(1)
            if param_name in values:
                v = values[param_name]
                return str(v) if v is not None else ""
            default = match.group(3)
            return default if default else ""
        return re.sub(pattern, replacer, html)

    async def generate_frame(
        self,
        title: str,
        text: str,
        image: str,
        ext: Optional[Dict[str, Any]] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """Generate a frame image from HTML template."""
        # Convert local path to file:// URI
        if image and not image.startswith(("http://", "https://", "data:", "file://")):
            img_path = Path(image)
            if not img_path.is_absolute():
                img_path = Path.cwd() / image
            if img_path.exists():
                image = img_path.as_uri()

        context = {"title": title, "text": text, "image": image}
        if ext:
            context.update(ext)

        html = self._replace_parameters(self.template, context)

        if output_path is None:
            output_path = f"output/frame_{uuid.uuid4().hex[:16]}.png"
        else:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # Use Playwright to render HTML to image
        from playwright.async_api import async_playwright

        tmp_html_path = None
        try:
            if self._browser is None or not self._browser.is_connected():
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
                )

            browser = self._browser
            page = await browser.new_page(
                viewport={"width": self.width, "height": self.height},
                device_scale_factor=1,
            )
            try:
                fd, tmp_html_path = tempfile.mkstemp(suffix=".html", prefix="pv_frame_")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(html)
                await page.goto(Path(tmp_html_path).as_uri(), wait_until="networkidle")
                await page.screenshot(path=output_path, type="png", omit_background=True)
            finally:
                await page.close()
                if tmp_html_path and os.path.exists(tmp_html_path):
                    os.unlink(tmp_html_path)

            return output_path
        except Exception as e:
            raise RuntimeError(f"HTML rendering failed: {e}")

    @classmethod
    async def close_browser(cls):
        if cls._browser:
            await cls._browser.close()
            cls._browser = None
        if cls._playwright:
            await cls._playwright.stop()
            cls._playwright = None
