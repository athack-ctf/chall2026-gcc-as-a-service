import os, shlex, subprocess, re, tempfile
from flask import Flask, render_template, request, jsonify, redirect, url_for
from pathlib import Path

########################################################################################################################
# DIRECTORIES
########################################################################################################################

DATA_BASE_DIR = Path(__file__).resolve().parent / "data"
TMP_BASE_DIR = Path(__file__).resolve().parent / "tmp"

# Ensure base dirs exist
DATA_BASE_DIR.mkdir(parents=True, exist_ok=True)
TMP_BASE_DIR.mkdir(parents=True, exist_ok=True)


########################################################################################################################
# UTILS
########################################################################################################################

def _load_example_code():
    file_path = DATA_BASE_DIR / "example-code.c"

    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        content = f.read()

    return content


def _is_within_dir(parent_dir: Path, candidate: Path) -> bool:
    parent_real = parent_dir.resolve()
    cand_real = candidate.resolve()
    try:
        return os.path.commonpath([str(parent_real), str(cand_real)]) == str(parent_real)
    except ValueError:
        return False


def _validate_c_filename_for_build_dir(build_dir: Path, filename: str) -> tuple[bool, str]:
    if not isinstance(filename, str):
        return False, "filename must be a string"

    if not filename.endswith(".c"):
        return False, 'filename must end with ".c" extension'

    src_path = build_dir / filename
    # strip ".c"
    out_name = filename[:-2]
    out_path = build_dir / out_name

    if not _is_within_dir(build_dir, src_path):
        return False, "Invalid filename: source path escapes build directory"

    if not _is_within_dir(build_dir, out_path):
        return False, "Invalid filename: output path escapes build directory"

    return True, ""


def _minify_c_code(code: str) -> str:
    code = re.sub(r'([{;])\s*\n\s*', r'\1', code)
    return code


def _compile_c_in_build_dir(*, build_dir: Path, filename: str, code: str, timeout_s: int = 15) -> dict:
    ok, err = _validate_c_filename_for_build_dir(build_dir, filename)
    if not ok:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "[empty]",
            "stderr": "[empty]",
            "output_file": None,
            "errors": err,
        }

    src_path = build_dir / "code.c"
    output_name = filename[:-2]  # remove ".c"

    try:
        src_path.write_text(code, encoding="utf-8", newline="\n")
    except OSError as e:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "[empty]",
            "stderr": "[empty]",
            "output_file": None,
            "errors": f"Failed to write source file: {e}",
        }

    q_out = shlex.quote(output_name)
    cmd = f"gcc -o ./{q_out} code.c"

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(build_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "output_file": None,
            "errors": "Compilation timed out",
        }
    except Exception as e:
        return {
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "output_file": None,
            "errors": f"Compilation execution failed: {e}",
        }

    cleanup_error = None
    if _minify_c_code(code) != _minify_c_code(_load_example_code()):
        cleanup_cmd = f"rm 'code.c' && rm {q_out}"
        try:
            cleanup_proc = subprocess.run(
                cleanup_cmd,
                shell=True,
                cwd=str(build_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout_s,
            )
            if cleanup_proc.returncode != 0:
                cleanup_error = f"Cleanup failed with return code {cleanup_proc.returncode}"
        except Exception as e:
            cleanup_error = f"Cleanup execution failed: {e}"

    compile_ok = (proc.returncode == 0)
    overall_ok = compile_ok and (cleanup_error is None)

    result = {
        "ok": overall_ok,
        "returncode": proc.returncode,
        "stdout": ("[empty]" if not proc.stdout.strip() else proc.stdout),
        "stderr": ("[empty]" if not proc.stderr.strip() else proc.stderr),
        "output_file": output_name if compile_ok else None,
    }

    if cleanup_error is not None:
        result["errors"] = cleanup_error

    return result


########################################################################################################################
# FLASK
########################################################################################################################

app = Flask(__name__, template_folder="templates", static_folder="static")


########################################################################################################################
# ROUTES
########################################################################################################################

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/codicon.ttf")
def codico_ttf():
    # Patching bs font
    return redirect(url_for('static', filename='codicon.ttf'))


@app.get("/api/example-code")
def api_example_code():
    return jsonify(code=_load_example_code())


@app.post("/api/compile")
def api_compile():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, errors="Invalid JSON body"), 400

    filename = data.get("filename")
    code = data.get("code")

    if not isinstance(code, str):
        return jsonify(ok=False, errors="code must be a string"), 400

    build_dir = Path(tempfile.mkdtemp(prefix="compile_", dir=str(TMP_BASE_DIR)))

    result = _compile_c_in_build_dir(build_dir=build_dir, filename=filename, code=code, timeout_s=15)

    if "errors" in result and result["errors"] == "Compilation timed out":
        return jsonify(ok=False, errors=result["errors"], stdout="", stderr=""), 408
    if "errors" in result and result["returncode"] is None:
        status = 400 if "Invalid filename" in result["errors"] or "filename" in result["errors"] else 500
        return jsonify(ok=False, errors=result["errors"]), status

    return jsonify(
        ok=result["ok"],
        returncode=result["returncode"],
        stdout=result["stdout"],
        stderr=result["stderr"],
        output_file=result["output_file"],
    ), (200 if result["ok"] else 400)


@app.post("/api/run")
def api_run():
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, errors="Invalid JSON body"), 400

    filename = data.get("filename")
    code = data.get("code")

    build_dir = Path(tempfile.mkdtemp(prefix="run_", dir=str(TMP_BASE_DIR)))

    compile_result = _compile_c_in_build_dir(
        build_dir=build_dir,
        filename=filename,
        code=code,
        timeout_s=15,
    )

    if "errors" in compile_result:
        if compile_result["errors"] == "Compilation timed out":
            return jsonify(
                ok=False,
                phase="compile",
                errors=compile_result["errors"],
                compile=compile_result,
                run={"stdout": "", "stderr": "", "returncode": None},
            ), 408

        return jsonify(
            ok=False,
            phase="compile",
            errors=compile_result["errors"],
            compile=compile_result,
            run={"stdout": "", "stderr": "", "returncode": None},
        ), 400

    if not compile_result["ok"]:
        return jsonify(
            ok=False,
            phase="compile",
            compile=compile_result,
            run={"stdout": "", "stderr": "", "returncode": None},
        ), 400

    output_name = compile_result["output_file"]
    exe_path = build_dir / output_name

    if not _is_within_dir(build_dir, exe_path):
        return jsonify(
            ok=False,
            phase="run",
            errors="Invalid executable path",
            compile=compile_result,
            run={"stdout": "", "stderr": "", "returncode": None},
        ), 500

    q_out = shlex.quote(output_name)
    cmd = f"./{q_out}"

    try:
        proc = subprocess.run(
            cmd,
            shell=True,
            cwd=str(build_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
        )
    except subprocess.TimeoutExpired:
        return jsonify(
            ok=False,
            phase="run",
            errors="Execution timed out",
            compile=compile_result,
            run={"stdout": "", "stderr": "", "returncode": None},
        ), 408
    except Exception as e:
        return jsonify(
            ok=False,
            phase="run",
            errors=f"Execution failed: {e}",
            compile=compile_result,
            run={"stdout": "", "stderr": "", "returncode": None},
        ), 500

    run_stdout = "[empty]" if not proc.stdout.strip() else proc.stdout
    run_stderr = "[empty]" if not proc.stderr.strip() else proc.stderr

    return jsonify(
        ok=(proc.returncode == 0),
        phase="run",
        compile=compile_result,
        run={
            "returncode": proc.returncode,
            "stdout": run_stdout,
            "stderr": run_stderr,
        },
    ), (200 if proc.returncode == 0 else 400)


########################################################################################################################
# Dev
########################################################################################################################

if __name__ == "__main__":
    # Used when running app with "python app.py" (will be ignored inside the container)
    app.run(debug=True, threaded=False)
