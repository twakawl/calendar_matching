"""Deployment configuration regression tests."""

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class DeploymentConfigTest(unittest.TestCase):
    def test_dockerfile_uses_uvicorn_not_fastapi_cli(self):
        """Fly.io should not start through the optional FastAPI CLI package."""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()

        self.assertNotIn("/app/.venv/bin/fastapi", dockerfile)
        self.assertIn("python -m uvicorn app:app", dockerfile)

    def test_dockerfile_defaults_to_fly_internal_port(self):
        """The container should listen on the port configured in fly.toml."""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        fly_toml = (REPO_ROOT / "fly.toml").read_text()

        self.assertIn("ENV PORT=8080", dockerfile)
        self.assertIn("--port ${PORT:-8080}", dockerfile)
        self.assertIn("internal_port = 8080", fly_toml)


if __name__ == "__main__":
    unittest.main()
