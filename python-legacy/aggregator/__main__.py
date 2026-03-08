"""Entry point: python -m aggregator."""

import uvicorn

from aggregator.config import get_settings


def main():
    settings = get_settings()
    uvicorn.run(
        "aggregator.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
