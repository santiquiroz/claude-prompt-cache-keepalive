import contextlib
import importlib.util
import io
import pathlib
import sys
from unittest import mock

sys.dont_write_bytecode = True
REPO = pathlib.Path(__file__).resolve().parents[1]


def load_script(relative_path):
    path = REPO / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_main(module, *args):
    out, err, code = io.StringIO(), io.StringIO(), 0
    argv = [f"{module.__name__}.py", *args]
    with mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            module.main()
        except SystemExit as exit_:
            code = exit_.code
    return code, out.getvalue(), err.getvalue()
