import * as monaco from "https://cdn.jsdelivr.net/npm/monaco-editor@0.50.0/+esm";

async function fetchExampleCode() {
    try {
        const r = await fetch("/api/example-code", {cache: "no-store"});
        if (!r.ok) throw new Error(`example-code failed (${r.status})`);
        const data = await r.json();
        if (typeof data?.code !== "string") throw new Error("example-code: bad JSON");
        return data.code;
    } catch {
        return "// add your code here...";
    }
}

const defaultCode = await fetchExampleCode();

const editor = monaco.editor.create(document.getElementById("editor"), {
    value: defaultCode,
    language: "cpp",
    theme: "vs-dark",
    automaticLayout: true,
    minimap: {enabled: false},
    fontSize: 14,
    tabSize: 2,
    insertSpaces: true,
});

function getFilename() {
    const raw = document.getElementById("filename").value.trim();
    const regex = /^[A-Za-z0-9\._-]+\.c$/;

    if (!regex.test(raw)) {
        alert("Invalid filename. Use only letters, numbers, dot, hyphen, or underscore and end it with .c extension");
        return null;
    }

    return raw;
}

function setCompileOutput(stdout, stderr, errors) {
    const el = document.getElementById("compileOutput");

    const out = [
        stdout ? `STDOUT:\n${stdout}` : "",
        stderr ? `STDERR:\n${stderr}` : "",
        errors ? `ERRORS:\n${errors}` : "",
    ]
        .filter(Boolean)
        .join("\n\n");

    el.textContent = out || "";
    el.classList.toggle("muted", !out);
}

function setRunOutput(stdout, stderr) {
    const el = document.getElementById("runOutput");
    const out = [
        stdout ? `STDOUT:\n${stdout}` : "",
        stderr ? `STDERR:\n${stderr}` : "",
    ]
        .filter(Boolean)
        .join("\n\n");
    el.textContent = out || "";
    el.classList.toggle("muted", !out);
}

async function postJSON(url, body) {
    const r = await fetch(url, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
    });

    let data = null;
    try {
        data = await r.json();
    } catch {
        data = null;
    }

    return {httpOk: r.ok, status: r.status, data};
}

// Very simple formatter (brace-based indentation)
function simpleBraceIndent(code, indent = "  ") {
    const lines = code.replace(/\r\n/g, "\n").split("\n");
    let level = 0;
    const out = [];

    for (let line of lines) {
        const trimmed = line.trim();
        if (trimmed.startsWith("}")) level = Math.max(0, level - 1);
        out.push(indent.repeat(level) + trimmed);
        if (trimmed.endsWith("{")) level++;
    }

    return out.join("\n");
}

document.getElementById("btnFormat").addEventListener("click", () => {
    const formatted = simpleBraceIndent(editor.getValue());
    editor.setValue(formatted);
    setCompileOutput("", "", "");
});

// Keep last compile result around (useful once /api/run is implemented)
let lastCompile = null;

document.getElementById("btnCompile").addEventListener("click", async () => {
    const filename = getFilename();
    if (!filename) return;

    setCompileOutput("", "", "Compiling...");
    setRunOutput("", ""); // clear run output on new compile

    const res = await postJSON("/api/compile", {
        filename,
        code: editor.getValue(),
    });

    const body = res.data && typeof res.data === "object" ? res.data : {};
    lastCompile = body;

    const stdout = typeof body.stdout === "string" ? body.stdout : "";
    const stderr = typeof body.stderr === "string" ? body.stderr : "";
    const errors = typeof body.errors === "string" ? body.errors : "";

    if (!("ok" in body) && !("stderr" in body) && !("stdout" in body) && !("errors" in body)) {
        setCompileOutput("", "", `Request failed (HTTP ${res.status}).`);
        return;
    }

    setCompileOutput(stdout, stderr, errors);

    const isEmpty =
        (!stdout || !stdout.trim()) &&
        (!stderr || !stderr.trim()) &&
        (!errors || !errors.trim());

    if (isEmpty) setCompileOutput("", "", "[no compiler output]");
});

document.getElementById("btnRun").addEventListener("click", async () => {
    const filename = getFilename();
    if (!filename) return;

    setRunOutput("", "Running...");

    const res = await postJSON("/api/run", {
        filename,
        code: editor.getValue(),
    });

    const body = res.data && typeof res.data === "object" ? res.data : {};

    // NEW: /api/run returns { ok, compile:{...}, run:{...}, errors? }
    const compile = body.compile && typeof body.compile === "object" ? body.compile : null;
    if (compile) {
        const cStdout = typeof compile.stdout === "string" ? compile.stdout : "";
        const cStderr = typeof compile.stderr === "string" ? compile.stderr : "";
        const cErrors = typeof compile.errors === "string" ? compile.errors : "";
        setCompileOutput(cStdout, cStderr, cErrors);
        lastCompile = compile;
    }

    const run = body.run && typeof body.run === "object" ? body.run : null;
    const stdout = run && typeof run.stdout === "string" ? run.stdout : "";
    const stderr = run && typeof run.stderr === "string" ? run.stderr : "";

    // If backend returned a top-level errors string, surface it in stderr area (same behavior as before)
    const errors = typeof body.errors === "string" ? body.errors : "";

    if (typeof body.ok === "boolean") {
        setRunOutput(stdout, stderr || errors);
        return;
    }

    setRunOutput("", `Request failed (${res.status}).`);
});
