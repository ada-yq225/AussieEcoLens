from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 7:
        raise SystemExit(
            "usage: render_web_config.py MODE API_BASE_URL COGNITO_DOMAIN CLIENT_ID REDIRECT_URI LOGOUT_URI"
        )
    _, mode, api_base_url, cognito_domain, client_id, redirect_uri, logout_uri = sys.argv
    config = {
        "mode": mode,
        "apiBaseUrl": api_base_url,
        "cognitoDomain": cognito_domain,
        "cognitoClientId": client_id,
        "redirectUri": redirect_uri,
        "logoutUri": logout_uri,
    }
    Path("web/config.js").write_text(
        "window.AUSSIE_CONFIG = " + json.dumps(config, indent=2) + ";\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

