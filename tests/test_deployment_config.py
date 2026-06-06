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

    def test_env_example_includes_fly_configuration(self):
        """The environment template should include Fly.io deployment fields."""
        env_example = (REPO_ROOT / ".env.example").read_text()

        self.assertIn("# Fly.io configuration (if deploying there)", env_example)
        self.assertIn("FLY_APP_NAME=", env_example)
        self.assertIn("FLY_REGION=", env_example)
        self.assertIn("FLY_SECRET_KEY=", env_example)

    def test_google_redirect_uri_is_read_directly_from_environment(self):
        """OAuth code should support explicit Google redirect URIs from env."""
        app_py = (REPO_ROOT / "app.py").read_text()

        self.assertIn('redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")', app_py)
        self.assertIn("REDIRECT_URI = _resolve_redirect_uri()", app_py)


if __name__ == "__main__":
    unittest.main()
