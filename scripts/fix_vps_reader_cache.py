import os
import re
import sys

import paramiko


HOST = "192.168.1.254"
PORT = 2222
USERNAME = "hieupt"
PASSWORD = os.environ.get("THREET_VPS_PASSWORD", "")
if not PASSWORD:
    sys.exit(
        "THREET_VPS_PASSWORD chưa được thiết lập.\n"
        'PowerShell: $env:THREET_VPS_PASSWORD = "<mật khẩu VPS>"'
    )

REMOTE_MAIN = "/home/hieupt/projects/3T_Reader/phase1-backend/server/license-api/app/main.py"
REMOTE_INDEX = "/home/hieupt/projects/3T_Reader/phase1-backend/server/license-api/app/static/index.html"
REMOTE_COMPOSE_DIR = "/home/hieupt/projects/3T_Reader/phase1-backend/infra/backend"

NEW_INDEX_ROUTE = """@app.get("/", response_class=HTMLResponse)
def index():
    from fastapi.responses import Response
    with open(_STATIC / "index.html", "rb") as f:
        html = f.read()
    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )"""


def run(ssh: paramiko.SSHClient, command: str) -> tuple[int, str, str]:
    stdin, stdout, stderr = ssh.exec_command(command)
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def read_remote(sftp: paramiko.SFTPClient, path: str) -> str:
    with sftp.open(path, "r") as f:
        return f.read().decode("utf-8")


def write_remote(sftp: paramiko.SFTPClient, path: str, content: str) -> None:
    with sftp.open(path, "w") as f:
        f.write(content.encode("utf-8"))


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(
        HOST,
        port=PORT,
        username=USERNAME,
        password=PASSWORD,
        timeout=15,
        banner_timeout=15,
    )
    try:
        sftp = ssh.open_sftp()
        main_py = read_remote(sftp, REMOTE_MAIN)
        if NEW_INDEX_ROUTE not in main_py:
            main_py, count = re.subn(
                r'@app\.get\("/", response_class=FileResponse\)\s+def index\(\):\s+return FileResponse\(_STATIC / "index\.html", media_type="text/html"\)',
                NEW_INDEX_ROUTE,
                main_py,
                count=1,
                flags=re.MULTILINE,
            )
            if count != 1:
                print("Did not find expected index route in remote main.py", file=sys.stderr)
                return 1
            write_remote(sftp, REMOTE_MAIN, main_py)
            print("Patched remote main.py")
        else:
            print("Remote main.py already patched")

        index_html = read_remote(sftp, REMOTE_INDEX)
        if "3TReader-1.0.18-win-r3.exe" not in index_html or "3TReader-1.0.18-win-portable-r3.zip" not in index_html:
            print("Remote index.html does not contain r3 links", file=sys.stderr)
            return 1
        print("Remote index.html already points to r3")
        sftp.close()

        code, out, err = run(
            ssh,
            f"cd {REMOTE_COMPOSE_DIR} && docker compose up -d --build license-api",
        )
        print(out)
        if code != 0:
            print(err, file=sys.stderr)
            return code

        code, out, err = run(
            ssh,
            "curl -s https://reader.3tcomputer.com | sed -n '236,248p'",
        )
        print(out)
        if code != 0:
            print(err, file=sys.stderr)
            return code

        code, out, err = run(
            ssh,
            "curl -I -s https://reader.3tcomputer.com",
        )
        print(out)
        if code != 0:
            print(err, file=sys.stderr)
            return code

        code, out, err = run(
            ssh,
            "curl -I -s https://reader.3tcomputer.com/downloads/3TReader-1.0.18-win-r3.exe",
        )
        print(out)
        if code != 0:
            print(err, file=sys.stderr)
            return code

        return 0
    finally:
        ssh.close()


if __name__ == "__main__":
    raise SystemExit(main())
