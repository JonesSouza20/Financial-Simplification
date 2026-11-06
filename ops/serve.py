"""Inicia o sistema: Waitress só em 127.0.0.1 e o agendador interno (ADR-011, ADR-017, ADR-018).

Usado pelo serviço do Windows (WinSW) ou pela tarefa "ao fazer logon" (plano B).
O Tailscale Serve publica esta porta com HTTPS só na sua rede privada (ADR-012).
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")


def configure(argv: list[str] | None = None) -> None:
    """Os scripts (install.ps1) passam os mesmos valores de ops/config.ps1 ao serviço."""
    import argparse

    parser = argparse.ArgumentParser(description="Servidor do sistema de finanças")
    parser.add_argument("--port", default=os.environ.get("FINANCAS_PORT", "8000"))
    parser.add_argument("--tailnet-host", default=os.environ.get("FINANCAS_TAILNET_HOST", ""))
    parser.add_argument("--data-dir", default=os.environ.get("FINANCAS_DATA_DIR", ""))
    args = parser.parse_args(argv)
    os.environ["FINANCAS_PORT"] = str(int(args.port))
    os.environ["FINANCAS_TAILNET_HOST"] = args.tailnet_host
    if args.data_dir:
        os.environ["FINANCAS_DATA_DIR"] = args.data_dir


def capture_output() -> None:
    """Com pythonw (tarefa do plano B) não há console: a saída vai para logs/serve.log."""
    if sys.stderr is not None and sys.stdout is not None:
        return
    data = Path(os.environ.get("FINANCAS_DATA_DIR") or ROOT / "var")
    (data / "logs").mkdir(parents=True, exist_ok=True)
    stream = open(data / "logs" / "serve.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    sys.stdout = sys.stderr = stream


def main() -> None:
    configure()
    capture_output()
    import django

    django.setup()
    from django.core.management import call_command

    call_command("check", deploy=False)
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    if executor.migration_plan(executor.loader.graph.leaf_nodes()):
        raise SystemExit("Há migrações pendentes. Rode ops\\update.ps1 (faz backup antes).")

    from apps.scheduler import jobs

    jobs.start()

    from waitress import serve

    from config.wsgi import application

    port = int(os.environ.get("FINANCAS_PORT", "8000"))
    serve(application, host="127.0.0.1", port=port, threads=8, ident="financas")


if __name__ == "__main__":
    main()
