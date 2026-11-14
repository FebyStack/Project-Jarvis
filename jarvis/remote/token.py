"""The bearer token every API route needs: `home/token`, mode 600, made once."""
import os
import secrets
from pathlib import Path


def load_token(home: Path) -> str:
    path = Path(home) / "token"
    if not path.exists():
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(32))
    return path.read_text().strip()
